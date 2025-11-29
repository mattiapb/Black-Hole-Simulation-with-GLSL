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


#esta constante la usare para escalar cosas, es el radio de schwarzchild, o el tamano del horizonte de eventos de Sagitario A*, hare que 1 uniad = 1 Sagitario A*
SCALE_FACTOR = 1.269e10

#definimos la camara, parametros de posicion, velocidad y sensibilidad, en un diccionario actualizable
camera_state = {
    'position': np.array([0.0, 2.0, 15.0]),
    'yaw': -np.pi / 2.0,
    'pitch': -0.1,
    'speed': 10.0,
    'sensitivity': 0.003
}

#definimos un diccionario de teclas (cada una con su ASCII entero), por que tuve un bug con el metodo convencional (quiza este es el convencional y lo descubri a la "mala"), todas en False, para actualizarse si se presiona una.
keys_down = {
    119: False, #key.W
    115: False, #key.S
    97:  False, #key.A
    100: False, #key.D
    32:  False, #key.SPACE
    65507: False #key.LCTRL
}

#inicializamos el tiempo que luego usaremos en iTime
app_start_time = time.time() 

#matematicas de la camara
def get_camera_vectors(state):

    #angulos a direccion
    fwd_x = np.cos(state['yaw']) * np.cos(state['pitch'])
    fwd_y = np.sin(state['pitch'])
    fwd_z = np.sin(state['yaw']) * np.cos(state['pitch'])
    
    #se convierte en array y sera nuestro vector adelante (hacia donde mira la camara)
    cam_fwd = np.array([fwd_x, fwd_y, fwd_z])

    #nos aseguramos de que sea de tamano 1
    if np.linalg.norm(cam_fwd) > 1e-6:
        cam_fwd = cam_fwd / np.linalg.norm(cam_fwd)

    #conocemos adelante, asi que definimos nuestro "arriba" (vector unitario Y)
    global_up = np.array([0.0, 1.0, 0.0])
    #nuestra "derecha" sera el producto cruz de arriba y adelante
    cam_right = np.cross(cam_fwd, global_up)

    #arreglamos el caso en que adelante es (0,1,0) y arriba es (0,1,0) (ie, miramos arriba), en este caso el producto cruz es cero y no existiria, se llama a una derecha auxiliar solo para el caso.
    if np.linalg.norm(cam_right) < 1e-6:
        if cam_fwd[1] > 0.99:
            cam_right = np.cross(np.array([0.0, 0.0, -1.0]), cam_fwd)
        else:
            cam_right = np.cross(np.array([0.0, 0.0, 1.0]), cam_fwd)
    
    #se estaba bugeando el cam_right (cuando miraba hacia un angulo de arriba o abajo pero no totalmente vertical se bugeaba), solucion: se normaliza
    cam_right = cam_right / np.linalg.norm(cam_right) 

    #definimos el arriba de la camara (no mundo), y lo normalizamos
    cam_up = np.cross(cam_right, cam_fwd)
    cam_up = cam_up / np.linalg.norm(cam_up) 

    #actualizamos el diccionario de camara y retornamos.
    cam_pos = state['position']
    return cam_pos, cam_fwd, cam_up, cam_right

#creamos el cuadrado que define la pantalla, con coordenadas NDC de -1 a 1 en XY como vimos en clases
def create_fullscreen_quad():
    vertices=np.array([-1.0,-1.0,0.0,1.0,-1.0,0.0,1.0,1.0,0.0,-1.0,1.0,0.0],dtype=np.float32)
    indices=np.array([0,1,2,2,3,0],dtype=np.uint32)
    return {"vertices":vertices,"indices":indices}


def main_task(width=1280, height=720):
    window=pyglet.window.Window(width,height,resizable=True,caption="Tarea 3: Agujero Negro") #creacion de la ventana del programa
    window.set_exclusive_mouse(True) #para el giro de camara, se atrapa el cursor (como en los juegos)

    #activamos alpha blending
    GL.glEnable(GL.GL_BLEND) 
    GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)

    #hice esto para probar resoluciones, pero no lo use
    compute_width = width
    compute_height = height

    #cargamos la pipeline (los shaders)
    pipeline=load_pipeline(Path(os.path.dirname(__file__))/"black_hole.vert",Path(os.path.dirname(__file__))/"black_hole.frag")


    quad_mesh_data=create_fullscreen_quad() #damos la pantalla (los dos triangulos o el cuadrado)

    gpu_quad=pipeline.vertex_list_indexed(len(quad_mesh_data["vertices"])//3,GL.GL_TRIANGLES,quad_mesh_data["indices"]) #reserva memoria en la gpu para guardar la info de la pantalla
    gpu_quad.aPos[:]=quad_mesh_data["vertices"] #pasamos de CPU a GPU los datos, aPos es la variable en el shader.


    #se carga la textura del disco de acrecion
    texture_path = Path(os.path.dirname(__file__)) / "disk_texture.png"
    #se pasa la imagen a la cpu (pyglet) y luego a la gpu como una textura
    disk_image = pyglet.image.load(texture_path)
    disk_texture = disk_image.get_texture()

    #parametrizacion de texturas en sus coordenadas (ademas de darle las opciones de que pasa si se pasa del borde)
    GL.glBindTexture(disk_texture.target, disk_texture.id)
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR) #filtros automaticos cuando uno se aleja, creo que es tipo mipmap automatico
    GL.glTexParameteri(disk_texture.target, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
    GL.glBindTexture(disk_texture.target, 0)

    #definimos las fuentes de luz tipo soles, de radio 3.75e10, normalizados por el factor de escala que se hablo al principio.
    light_source_1_pos_rad=np.array([4e11/SCALE_FACTOR,0.0,0.0,3.75e10/SCALE_FACTOR],dtype=np.float32)
    light_source_1_color=np.array([1.0,1.0,1.0],dtype=np.float32)
    light_source_2_pos_rad=np.array([0.0,0.0,4e11/SCALE_FACTOR,3.75e10/SCALE_FACTOR],dtype=np.float32)
    light_source_2_color=np.array([1.0,1.0,1.0],dtype=np.float32)
    
    #esto es para definir si se atrapo el mouse, o si se apreto esc y se dejo de atrapar
    is_mouse_captured=True

    @window.event
    def on_mouse_motion(x,y,dx,dy): #dy y dx actualizan posicion
        if is_mouse_captured: #si el mouse esta atrapado en la ventana
            sens=camera_state['sensitivity']
            camera_state['yaw']+=dx*sens
            camera_state['pitch']+=dy*sens
            camera_state['pitch']=np.clip(camera_state['pitch'],-np.pi/2+0.01,np.pi/2-0.01) #este da un limite para no pasar atras de la cabeza y se den vuelta los ejes

    #opcion para aumentar velocidad de la camara con el scroll
    @window.event
    def on_mouse_scroll(x,y,scroll_x,scroll_y):
        speed_factor=1.2
        if scroll_y>0: camera_state['speed']*=speed_factor
        elif scroll_y<0: camera_state['speed']/=speed_factor
        camera_state['speed']=np.clip(camera_state['speed'],0.01,100.0) #limites de velocidad 0.01 y 100.0

    #se presiono la tecla?
    @window.event
    def on_key_press(symbol,modifiers):
        nonlocal is_mouse_captured
        if symbol==key.ESCAPE: #solo si se presiono escape
            is_mouse_captured=not is_mouse_captured
            window.set_exclusive_mouse(is_mouse_captured)
            for k in keys_down: keys_down[k]=False
            return pyglet.event.EVENT_HANDLED

        if symbol in keys_down:
            keys_down[symbol]=True
    
    @window.event
    def on_key_release(symbol, modifiers):
        #registro seguro de si la tecla es soltada
        if symbol in keys_down:
            keys_down[symbol] = False

    #para mover la camara
    def update_camera(dt):
        dt=min(dt,0.1) #limitamos el dt porseacaso
        cam_pos,cam_fwd,cam_up,cam_right=get_camera_vectors(camera_state) #orientacion actual
        current_speed=camera_state['speed']*dt #cantidad de movimiento
        move_vector=np.array([0.0,0.0,0.0]) #empieza en cero y registra la suma de posiciones en un dt

        #si una tecla esta presionada se le suma cantidad de posicion al vector de movimiento
        if keys_down[119]: move_vector+=cam_fwd*current_speed #W
        if keys_down[115]: move_vector-=cam_fwd*current_speed #S
        if keys_down[97]: move_vector-=cam_right*current_speed #A
        if keys_down[100]: move_vector+=cam_right*current_speed #D
        if keys_down[32]: move_vector[1]+=current_speed #Space
        if keys_down[65507]: move_vector[1]-=current_speed #LCtrl

        #actualizamos posicion de la camara
        camera_state['position']+=move_vector

    pyglet.clock.schedule_interval(update_camera,1/60.0)

    #redibujado de ventana para la gpu
    @window.event
    def on_draw():
        GL.glClear(GL.GL_COLOR_BUFFER_BIT|GL.GL_DEPTH_BUFFER_BIT) #borra los buffers de color y profundidad
        pipeline.use() #activar pipeline de shaders
        cam_pos,cam_fwd,cam_up,cam_right=get_camera_vectors(camera_state) #donde esta la camara


        GL.glActiveTexture(GL.GL_TEXTURE0) #ranura 0 de texturas en la gpu seleccionada, es un puntero
        GL.glBindTexture(disk_texture.target, disk_texture.id) #pone la imagen del disco en la ranura 0
        pipeline["iDiskTexture"] = 0 #le dice al shader que la textura esta en la ranura 0

        #le pasamos las resoluciones, creo que en un principio basta con resolution, hice la otra probar optimizaciones
        pipeline["iResolution"]=np.array([window.width,window.height],dtype=np.float32)
        pipeline["iComputeResolution"]=np.array([compute_width,compute_height],dtype=np.float32)

        pipeline["iTime"] = time.time() - app_start_time #variable de tiempo

        #posiciones y orientaciones de la camara (para que el shader sepa lanzar los rayos de luz)
        pipeline["iCamPos"] = cam_pos
        pipeline["iCamFwd"]=cam_fwd
        pipeline["iCamUp"]=cam_up
        pipeline["iCamRight"]=cam_right

        #posicion y colores de los soles
        pipeline["iLight1PosRad"]=light_source_1_pos_rad
        pipeline["iLight1Color"]=light_source_1_color
        pipeline["iLight2PosRad"]=light_source_2_pos_rad
        pipeline["iLight2Color"]=light_source_2_color

        #dibujado de triangulos definidos
        gpu_quad.draw(GL.GL_TRIANGLES)
        
        #se desvincula la textura para limpiar para el siguiente frame
        GL.glBindTexture(disk_texture.target, 0)

    pyglet.app.run()

if __name__=="__main__":
    main_task()