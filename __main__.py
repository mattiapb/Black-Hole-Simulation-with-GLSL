import os
import sys
import numpy as np
import pyglet
import pyglet.gl as GL
from pyglet.window import key
from pathlib import Path
import time

from .grafica import transformations as tr
from .grafica.utils import load_pipeline


# Schwarzschild radius of Sagittarius A* in meters.
# Used to normalize astronomical distances to a coordinate system manageable by the GPU.
SCALE_FACTOR = 1.269e10

# Dictionary defining the camera's state: position, orientation (Euler angles), and movement parameters.
camera_state = {
    'position': np.array([0.0, 2.0, 15.0]),
    'yaw': -np.pi / 2.0,
    'pitch': -0.1,
    'speed': 10.0,
    'sensitivity': 0.003
}

# Input state registry using raw key codes.
# Maps specific key IDs to their active state (True/False).
keys_down = {
    119: False, # key.W
    115: False, # key.S
    97:  False, # key.A
    100: False, # key.D
    32:  False, # key.SPACE
    65507: False # key.LCTRL
}

# Application start timestamp, used to calculate the 'iTime' uniform for shader animations.
app_start_time = time.time() 

def get_camera_vectors(state):
    """
    Calculates the orthonormal basis vectors (Forward, Up, Right) for the camera
    based on its current Yaw and Pitch angles.
    """

    # Convert spherical coordinates (Yaw/Pitch) to a Cartesian direction vector.
    fwd_x = np.cos(state['yaw']) * np.cos(state['pitch'])
    fwd_y = np.sin(state['pitch'])
    fwd_z = np.sin(state['yaw']) * np.cos(state['pitch'])
    
    # Create the Forward vector.
    cam_fwd = np.array([fwd_x, fwd_y, fwd_z])

    # Ensure the Forward vector is normalized.
    if np.linalg.norm(cam_fwd) > 1e-6:
        cam_fwd = cam_fwd / np.linalg.norm(cam_fwd)

    # Define the Global Up vector.
    global_up = np.array([0.0, 1.0, 0.0])
    
    # Calculate the Right vector via cross product.
    cam_right = np.cross(cam_fwd, global_up)

    # Handle Singularity (Gimbal Lock): 
    # If the camera looks straight up or down, Forward and Global Up are parallel, 
    # resulting in a zero cross product. We use an arbitrary axis to resolve this.
    if np.linalg.norm(cam_right) < 1e-6:
        if cam_fwd[1] > 0.99:
            cam_right = np.cross(np.array([0.0, 0.0, -1.0]), cam_fwd)
        else:
            cam_right = np.cross(np.array([0.0, 0.0, 1.0]), cam_fwd)
    
    # Normalize the Right vector to prevent FOV distortion or "zooming" artifacts 
    # caused by non-unit vectors.
    cam_right = cam_right / np.linalg.norm(cam_right) 

    # Calculate the local Camera Up vector and normalize it.
    cam_up = np.cross(cam_right, cam_fwd)
    cam_up = cam_up / np.linalg.norm(cam_up) 

    # Return the updated camera vectors.
    cam_pos = state['position']
    return cam_pos, cam_fwd, cam_up, cam_right

def create_fullscreen_quad():
    """
    Generates the geometry for a full-screen quad using Normalized Device Coordinates (NDC).
    This acts as the canvas for the Ray Marching fragment shader.
    """
    vertices=np.array([-1.0,-1.0,0.0,1.0,-1.0,0.0,1.0,1.0,0.0,-1.0,1.0,0.0],dtype=np.float32)
    indices=np.array([0,1,2,2,3,0],dtype=np.uint32)
    return {"vertices":vertices,"indices":indices}


def main_task(width=1280, height=720):
    window=pyglet.window.Window(width,height,resizable=True,caption="Tarea 3: Agujero Negro") 
    window.set_exclusive_mouse(True) # Lock and hide the mouse cursor for FPS-style control.

    # Enable Alpha Blending for proper transparency rendering.
    GL.glEnable(GL.GL_BLEND) 
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

    # Define internal compute resolution (can be downscaled for performance optimization).
    compute_width = width // 320
    compute_height = height // 320

    # Load and compile the shader pipeline.
    pipeline=load_pipeline(Path(os.path.dirname(__file__))/"black_hole.vert",Path(os.path.dirname(__file__))/"black_hole.frag")


    quad_mesh_data=create_fullscreen_quad() 

    # Allocate GPU memory and upload vertex data.
    gpu_quad=pipeline.vertex_list_indexed(len(quad_mesh_data["vertices"])//3,GL.GL_TRIANGLES,quad_mesh_data["indices"]) 
    gpu_quad.aPos[:]=quad_mesh_data["vertices"] 


    # --- Texture Loading ---
    texture_path = Path(os.path.dirname(__file__)) / "disk_texture.png"
    # Load image to CPU memory and generate an OpenGL texture.
    disk_image = pyglet.image.load(texture_path)
    disk_texture = disk_image.get_texture()

    # Configure texture parameters (wrapping and filtering).
    GL.glBindTexture(disk_texture.target, disk_texture.id)
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR) # Linear filtering for smooth scaling.
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glBindTexture(disk_texture.target, 0) # Unbind texture.

    # Define light sources (Stars) with position and radius, normalized by the scale factor.
    light_source_1_pos_rad=np.array([4e11/SCALE_FACTOR,0.0,0.0,3.75e10/SCALE_FACTOR],dtype=np.float32)
    light_source_1_color=np.array([1.0,1.0,1.0],dtype=np.float32)
    light_source_2_pos_rad=np.array([0.0,0.0,4e11/SCALE_FACTOR,3.75e10/SCALE_FACTOR],dtype=np.float32)
    light_source_2_color=np.array([1.0,1.0,1.0],dtype=np.float32)
    
    # Flag to track if the mouse is currently captured by the window.
    is_mouse_captured=True

    @window.event
    def on_mouse_motion(x,y,dx,dy): 
        # Update camera yaw and pitch based on mouse deltas.
        if is_mouse_captured: 
            sens=camera_state['sensitivity']
            camera_state['yaw']+=dx*sens
            camera_state['pitch']+=dy*sens
            # Clamp pitch to prevent the camera from flipping upside down.
            camera_state['pitch']=np.clip(camera_state['pitch'],-np.pi/2+0.01,np.pi/2-0.01) 

    @window.event
    def on_mouse_scroll(x,y,scroll_x,scroll_y):
        # Adjust movement speed dynamically using the scroll wheel.
        speed_factor=1.2
        if scroll_y>0: camera_state['speed']*=speed_factor
        elif scroll_y<0: camera_state['speed']/=speed_factor
        camera_state['speed']=np.clip(camera_state['speed'],0.01,100.0) 

    @window.event
    def on_key_press(symbol,modifiers):
        nonlocal is_mouse_captured
        # Toggle mouse capture with the ESC key.
        if symbol==key.ESCAPE: 
            is_mouse_captured=not is_mouse_captured
            window.set_exclusive_mouse(is_mouse_captured)
            # Reset all keys to avoid "sticky" movement when untabbing/pausing.
            for k in keys_down: keys_down[k]=False
            return pyglet.event.EVENT_HANDLED

        # Register key press in the input state dictionary.
        if symbol in keys_down:
            keys_down[symbol]=True
    
    @window.event
    def on_key_release(symbol, modifiers):
        # Update input state on key release.
        if symbol in keys_down:
            keys_down[symbol] = False

    def update_camera(dt):
        """Updates camera position based on input state and delta time."""
        dt=min(dt,0.1) # Cap delta time to prevent large jumps during lag spikes.
        cam_pos,cam_fwd,cam_up,cam_right=get_camera_vectors(camera_state) 
        current_speed=camera_state['speed']*dt 
        move_vector=np.array([0.0,0.0,0.0]) 

        # Update movement vector based on active keys.
        if keys_down[119]: move_vector+=cam_fwd*current_speed # W
        if keys_down[115]: move_vector-=cam_fwd*current_speed # S
        if keys_down[97]: move_vector-=cam_right*current_speed # A
        if keys_down[100]: move_vector+=cam_right*current_speed # D
        if keys_down[32]: move_vector[1]+=current_speed # SPACE
        if keys_down[65507]: move_vector[1]-=current_speed # LCTRL

        # Apply movement to the camera position.
        camera_state['position']+=move_vector

    # Schedule the camera update function to run 60 times per second.
    pyglet.clock.schedule_interval(update_camera,1/60.0)

    @window.event
    def on_draw():
        # Clear color and depth buffers before drawing.
        GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT) 
        pipeline.use() 
        
        # Get current camera orientation.
        cam_pos,cam_fwd,cam_up,cam_right=get_camera_vectors(camera_state) 


        # Bind texture to texture unit 0.
        GL.glActiveTexture(GL.GL_TEXTURE0) 
        GL.glBindTexture(disk_texture.target, disk_texture.id) 
        pipeline["iDiskTexture"] = 0 

        # Send resolution uniforms to the shader.
        pipeline["iResolution"]=np.array([window.width,window.height],dtype=np.float32)
        pipeline["iComputeResolution"]=np.array([compute_width,compute_height],dtype=np.float32)

        # Send elapsed time for animations.
        pipeline["iTime"] = time.time() - app_start_time 

        # Send camera vectors (for Ray Marching ray generation).
        pipeline["iCamPos"] = cam_pos
        pipeline["iCamFwd"]=cam_fwd
        pipeline["iCamUp"]=cam_up
        pipeline["iCamRight"]=cam_right

        # Send light source data.
        pipeline["iLight1PosRad"]=light_source_1_pos_rad
        pipeline["iLight1Color"]=light_source_1_color
        pipeline["iLight2PosRad"]=light_source_2_pos_rad
        pipeline["iLight2Color"]=light_source_2_color

        # Draw the screen quad.
        gpu_quad.draw(GL.GL_TRIANGLES)
        
        # Unbind texture.
        GL.glBindTexture(disk_texture.target, 0)

    pyglet.app.run()

if __name__=="__main__":
    main_task()
