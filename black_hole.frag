#version 330 core

out vec4 FragColor;  // color final del pixel
in vec2 fragCoord; // coordenadas de pixel que vienen del vert shader

uniform vec2 iResolution;
uniform vec2 iComputeResolution;
uniform vec3 iCamPos;
uniform vec3 iCamFwd;
uniform vec3 iCamUp;
uniform vec3 iCamRight;
uniform vec4 iLight1PosRad;
uniform vec3 iLight1Color;
uniform vec4 iLight2PosRad;
uniform vec3 iLight2Color;
uniform sampler2D iDiskTexture;
uniform sampler2D iBackgroundTexture; // esto era para poner textura al fondo pero no se uso
uniform float iTime;
uniform bool iHasBackgroundTexture; // esto era para poner textura al fondo pero no se uso

const float SagA_rs = 1.0; // radio de schwarzchild, lo fijamos en 1 ya que normalizamos con el radio real, es nuestra unidad de medida
const float PI = 3.14159265359; // pi


// definimos el estado del rayo, su posicion y velocidad ya que usaremos verlet como integrador
struct RayState {
    vec3 pos; 
    vec3 vel; 
};

// variables que se definen cuando un rayo choca a algo
vec4 objectColor = vec4(0.0); // color del objeto
vec3 hitCenter = vec3(0.0); // centro del objeto
float hitRadius = 0.0; // tamano del objeto


// esta funcion calcula como el agujero tira el rayo de luz para curvarlo
vec3 getAcceleration(vec3 pos) {
    float r = length(pos); // distancia desde el centro del agujero hasta el rayo
    if (r < 0.001) return vec3(0.0);  // no queremos que pase por 0 (singularidad, ocurre una division por 0 en la ec de schwarzchild) asi que lo truncamos a 0.001
    float factor = -1.5 * SagA_rs; //fuerza de atraccion, 1.5 para simular el comportamiento de la luz de manera simplificada
    return factor * pos / pow(r, 5.0) * dot(pos, pos); // es la fuerza de gravedad simplificada que se usa para optimizar estas simulaciones
}

// detector de si un rayo intercepto el agujero negro para eliminarlo despues (se lo traga)
bool interceptBlackHole(vec3 pos, float rs) {
    return length(pos) <= rs * 1.5;
}


// comprueba si el rayo golpea un objeto de luz, bool
bool interceptObject(vec3 pos) {
    vec3 c1 = iLight1PosRad.xyz; float r1 = iLight1PosRad.w; //extrae posicion del centro y tamano del radio del primer sol
    if (distance(pos, c1) <= r1) { objectColor=vec4(iLight1Color,1.0); hitCenter=c1; hitRadius=r1; return true; } //calcula distancia entre rayo y centro del sol, si es menor al radio significa que hay impacto
    
    vec3 c2 = iLight2PosRad.xyz; float r2 = iLight2PosRad.w; //extrae posicion del centro y tamano del radio del segundo sol
    if (distance(pos, c2) <= r2) { objectColor=vec4(iLight2Color,1.0); hitCenter=c2; hitRadius=r2; return true; } //calcula distancia entre rayo y centro del sol, si es menor al radio significa que hay impacto
    return false;
}

//fn principal
void main()
{
    vec2 computePixCoord = fragCoord * iComputeResolution; //calculamos en que pixel estamos dentro de la imagen, fragcoord va de 0,0 a 1,0, por la resolucion nos da la coord real
    //convertimos las coordenadas xy de un pixel a rango normalizado -1.0 a 1.0, el +0.5 es para apuntar al centro del pixel
    float compute_u_norm = ( (computePixCoord.x + 0.5) / iComputeResolution.x * 2.0 - 1.0); 
    float compute_v_norm = ( (computePixCoord.y + 0.5) / iComputeResolution.y * 2.0 - 1.0);

    float tanHalfFov = 0.577; // FOV, que tanta es la apertura de la camara
    float aspect = iResolution.x / iResolution.y; // proporcion de la imagen para que no veamos la escena estirada

    float u = compute_u_norm * aspect * tanHalfFov; // se ajusta la coord horizontal (u) agregandole el factor de aspecto y fov
    float v = compute_v_norm * tanHalfFov; // se ajusta la coord vertical (v) agregandole el factor de fov

    //!!! construimos el vector 3D del rayo, combinando vectores de la camara (derecha,arriba,adelante) ponderados por u, normalizandolo para que quede de long 1
    vec3 dir = normalize(u * iCamRight + v * iCamUp + iCamFwd);

    vec3 currPos = iCamPos; //el rayo empieza desde la camara
    vec3 currVel = dir; //la velocidad inicial del rayo es la direccion del rayo
    
    vec3 accumulatedColor = vec3(0.0); //color que acumula el rayo, empieza en negro 0.0
    float transmission = 1.0; //cuanta luz puede pasar a traves del rayo, 1.0 es transparente (camino limpio), si choca con el disco semitransparente ese valor baja

    int steps = 2000; //n de pasos del bucle for
    float dt = 0.05; // cada cuanto avanza el rayo
    float escape_r = 5000.0; //distancia de escape del rayo

    float disk_r1 = 1.9; // radio interno del disco de acrecion
    float disk_r2 = 7.0; // radio externo del disco de acrecion

    for (int i = 0; i < steps; ++i) { //bucle de tamano steps que nos dara el viaje del rayo por el espacio
        vec3 prevPos = currPos; //para guardar posicion 

        // verlet:
        vec3 acc = getAcceleration(currPos); // usamos la funcion de aceleracion que definimos antes
        currPos += currVel * dt + 0.5 * acc * dt * dt; // usamos verlet para definir la posicion y actualizarla
        vec3 newAcc = getAcceleration(currPos); //definimos la nueva actualizacion segun la posicion actualizada
        currVel += 0.5 * (acc + newAcc) * dt; //actualizamos la velocidad

        //if verificador para terminar el bucle de los rayos que caigan en el horizonte de sucesos
        if (interceptBlackHole(currPos, SagA_rs)) { 
            transmission = 0.0; 
            break; 
        }


        if (prevPos.y * currPos.y < 0.0) { // esta condicion nos dice que y es negativo, es decir, cruzo el 0

            //interpolamos la posicion exacta donde Y=0
            float t = abs(prevPos.y) / (abs(prevPos.y) + abs(currPos.y));
            vec3 crossingPoint = mix(prevPos, currPos, t);

            float r = length(vec2(crossingPoint.x, crossingPoint.z)); //que tan lejos del centro del agujero negro ocurrio ese cruce
            
            if (r >= disk_r1 && r <= disk_r2) { //esta dentro del disco de acrecion?
                if (length(currPos) > SagA_rs * 1.1) { //esto es para no dibujar el disco si el rayo esta muy cerca
                    // mapeo uv, se calcula el angulo donde fue el golpe, se le suma el tiempo para que la textura gire
                    float hit_angle_raw = atan(crossingPoint.z, crossingPoint.x);
                    float rotation_speed = 0.05;
                    float hit_angle = hit_angle_raw + iTime * rotation_speed;
                    
                    //hacemos un v radial, un radio con coordenada del 0 al 1 para leer textura
                    float v_radial = (r - disk_r1) / (disk_r2 - disk_r1);
                    v_radial = clamp(v_radial, 0.0, 1.0);
                    
                    //se ajusta v para que coincida mejor con el png
                    float texture_hole_norm = disk_r1 / disk_r2;
                    float v_texture = mix(texture_hole_norm, 1.0, v_radial);
                    
                    //esto da las coordenadas de texturas uv finales en coordenadas rectangulares de 0 a 1 para leer la imagen png
                    vec2 uv = vec2(0.5 + v_texture * cos(hit_angle + PI) * 0.5, 
                                   0.5 + v_texture * sin(hit_angle + PI) * 0.5);
                    uv.y = 1.0 - uv.y;
                    
                    vec4 texColor = texture(iDiskTexture, uv); //lee color y alfa de cada pixel del png

                    // se suavizan en alpha los bordes interior y exterior para evitar cortes bruscos que se vean feos.
                    float alpha = smoothstep(0.0, 0.1, v_radial) * smoothstep(1.0, 0.9, v_radial);
                    alpha *= texColor.a;

                    accumulatedColor += texColor.rgb * alpha * transmission; //se suma el color del disco a la imagen final, ademas se multiplica por transmission ya que si ya pasamos por algo opaco sumaria menos luz
                    transmission *= (1.0 - alpha); //hacemos que transmission dependa de la opacidad o el alpha del disco
                    if (transmission < 0.01) break; //si es casi cero dejamos de calcular para ahorrar rendimiento
                }
            }
        }

        //para que las estrellas se vean algo mas que un circulo plano
        if (interceptObject(currPos)) {  //el rayo esta tocando alguna de las esferas de luz?
            vec3 N = normalize(currPos - hitCenter); //currPos es la posicion de impacto, hitcenter es el centro de la esfera, su resta da un vector tipo normal pero no normalizado, se normaliza.
            vec3 V = normalize(iCamPos - currPos); // posicion de impacto hacia la camara normalizada
            float diff = max(dot(N, V), 0.0); // se le aplica iluminacion difusa como vimos en iluminacion de phong
            vec3 shadedColor = objectColor.rgb * (0.2 + 0.8 * diff); //el color sera el color del objeto por la suma de 0.2 (una componente ambiente) y 0.8*(componente difusa)
            
            accumulatedColor += shadedColor * transmission; // sumamos el color de la estrella multiplicado por la transmission que dice si es que esta atras del disco, la estrella se vera mas apagada
            transmission = 0.0; //las estrellas son opacas
            break; 
        }
        
        
    }
    
    FragColor = vec4(accumulatedColor, 1.0); //todo lo que hicimos para la pantalla
}