# Real-time Black Hole Simulator

A real-time visualization of a Schwarzschild black hole rendered using **Ray Marching** in OpenGL (GLSL) and Python.

This project simulates the physical phenomenon of **Gravitational Lensing**, where light from background stars and the accretion disk is bent by the immense gravity of the black hole. It uses a custom physics engine running entirely on the GPU (Fragment Shader) with adaptive step sizes for high performance.

## Features

* **Gravitational Lensing:** Real-time distortion of light rays based on General Relativity geodesics.
* **Volumetric Accretion Disk:** A texturized, rotating disk with soft alpha blending and intersection logic.
* **Free Camera:** Full WASD + Mouse control to fly around the black hole.

## Requirements

To run this simulation, you need the following installed on your system:

### Software
* **Python 3.8** or higher.
* **OpenGL 3.3** compatible Graphics Card (GPU).

### Python Dependencies
You need to install the required libraries. You can install them via pip:

```bash
pip install pyglet numpy
```
## Project Structure & Credits

This project includes the grafica module, which provides essential utilities for shader loading and transformations. This module is part of the course material for CC3501 - Computer Graphics at Universidad de Chile and originates from the following repository:

* Original Repository: [PLUMAS-research/cc3501-computer-graphics](https://github.com/PLUMAS-research/cc3501-computer-graphics)

The directory structure is organized as follows:

* Black-Hole/            <-- Root of the module
* grafica/           <-- Course library (Included)
* __main__.py        <-- Main application script
* black_hole.vert    <-- Vertex Shader
* black_hole.frag    <-- Fragment Shader (Physics Engine)
* disk_texture.png   <-- Accretion disk texture

## How to Run

To execute the simulation properly, you must run it as a Python module from the directory containing the Black-Hole folder.

1. Open your terminal or command prompt.

2. Navigate to the parent directory of the Black-Hole folder.

3. Run the following command:

```bash
  python -m Black-Hole-Simulation-with-GLSL-main
```
_(or the name you gave to the containing folder)_
## Controls

* **Mouse:**	Look around (Rotate Camera)
* **W, A, S, D:**	Move Camera (Forward, Left, Back, Right)
* **Space:**	Move Up (Global Y)
* **Left Ctrl:**	Move Down (Global Y)
* **Mouse Scroll:**	Adjust Movement Speed (Slower/Faster)
* **ESC:**	Release/Capture Mouse Cursor

_Developed for the Computer Graphics course (CC3501) at Universidad de Chile._
