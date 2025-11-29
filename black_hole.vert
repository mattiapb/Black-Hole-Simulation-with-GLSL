#version 330 core

layout (location = 0) in vec3 aPos;

//pasamos fragCoord al fragment shader
out vec2 fragCoord;

void main()
{
    //mapeamos aPos -1, 1 a fragCoord 0, 1
    fragCoord = aPos.xy * 0.5 + 0.5;
    gl_Position = vec4(aPos, 1.0);
}