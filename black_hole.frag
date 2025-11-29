#version 330 core

// Final pixel color output
out vec4 FragColor;

// Pixel coordinates from vertex shader (normalized 0.0-1.0)
in vec2 fragCoord;

// Uniform variables
uniform vec2 iResolution;           // Viewport resolution
uniform vec2 iComputeResolution;    // Computation resolution
uniform vec3 iCamPos;               // Camera position in world space
uniform vec3 iCamFwd;               // Camera forward vector
uniform vec3 iCamUp;                // Camera up vector
uniform vec3 iCamRight;             // Camera right vector
uniform vec4 iLight1PosRad;         // Light 1: xyz=position, w=radius
uniform vec3 iLight1Color;          // Light 1 color (RGB)
uniform vec4 iLight2PosRad;         // Light 2: xyz=position, w=radius
uniform vec3 iLight2Color;          // Light 2 color (RGB)
uniform sampler2D iDiskTexture;     // Accretion disk texture
uniform sampler2D iBackgroundTexture; // Background texture (unused)
uniform float iTime;                // Time uniform for animations
uniform bool iHasBackgroundTexture; // Background texture flag (unused)

// Physical constants
const float SagA_rs = 1.0;          // Schwarzschild radius (normalization unit)
const float PI = 3.14159265359;     // Mathematical constant π

// Ray state structure for numerical integration
struct RayState {
    vec3 pos;     // Current ray position
    vec3 vel;     // Current ray velocity/direction
};

// Intersection result variables
vec4 objectColor = vec4(0.0);       // Color of intersected object
vec3 hitCenter = vec3(0.0);         // Center of intersected object  
float hitRadius = 0.0;              // Radius of intersected object

/**
 * Calculates gravitational acceleration at given position
 * Simplified Schwarzschild metric approximation for light bending
 */
vec3 getAcceleration(vec3 pos) {
    float r = length(pos);                    // Distance from black hole center
    if (r < 0.001) return vec3(0.0);         // Avoid singularity at origin
    
    float factor = -1.5 * SagA_rs;           // Gravitational strength coefficient
    return factor * pos / pow(r, 5.0) * dot(pos, pos); // Inverse power law acceleration
}

/**
 * Detects if ray intersects black hole event horizon
 */
bool interceptBlackHole(vec3 pos, float rs) {
    return length(pos) <= rs * 1.5;          // Event horizon boundary check
}

/**
 * Tests ray intersection with light objects (stars)
 * Returns true if intersection occurs, sets object properties
 */
bool interceptObject(vec3 pos) {
    // Test light source 1
    vec3 c1 = iLight1PosRad.xyz; 
    float r1 = iLight1PosRad.w;
    if (distance(pos, c1) <= r1) { 
        objectColor = vec4(iLight1Color, 1.0); 
        hitCenter = c1; 
        hitRadius = r1; 
        return true; 
    } 
    
    // Test light source 2
    vec3 c2 = iLight2PosRad.xyz; 
    float r2 = iLight2PosRad.w;
    if (distance(pos, c2) <= r2) { 
        objectColor = vec4(iLight2Color, 1.0); 
        hitCenter = c2; 
        hitRadius = r2; 
        return true; 
    }
    return false;
}

/**
 * Main fragment shader function
 * Implements ray marching with gravitational lensing simulation
 */
void main()
{
    // Convert normalized coordinates to pixel coordinates
    vec2 computePixCoord = fragCoord * iComputeResolution;
    
    // Transform to normalized device coordinates (-1 to 1)
    float compute_u_norm = ((computePixCoord.x + 0.5) / iComputeResolution.x * 2.0 - 1.0);
    float compute_v_norm = ((computePixCoord.y + 0.5) / iComputeResolution.y * 2.0 - 1.0);

    // Camera projection parameters
    float tanHalfFov = 0.577;                // Field of view tangent
    float aspect = iResolution.x / iResolution.y; // Viewport aspect ratio

    // Calculate ray direction in camera space
    float u = compute_u_norm * aspect * tanHalfFov;
    float v = compute_v_norm * tanHalfFov;
    
    // Construct normalized world space ray direction
    vec3 dir = normalize(u * iCamRight + v * iCamUp + iCamFwd);

    // Initialize ray state
    vec3 currPos = iCamPos;                  // Ray origin at camera position
    vec3 currVel = dir;                      // Initial ray direction
    
    // Rendering state
    vec3 accumulatedColor = vec3(0.0);       // Accumulated color along ray path
    float transmission = 1.0;                // Light transmission coefficient (1.0 = fully transparent)

    // Ray marching parameters
    int steps = 2000;                        // Maximum ray marching steps
    float dt = 0.05;                         // Integration time step
    float escape_r = 5000.0;                 // Ray escape distance threshold
    
    // Accretion disk geometry
    float disk_r1 = 1.9;                     // Inner disk radius
    float disk_r2 = 7.0;                     // Outer disk radius

    // Main ray marching loop
    for (int i = 0; i < steps; ++i) {
        vec3 prevPos = currPos;              // Store previous position for interpolation

        // Verlet integration for numerical stability
        vec3 acc = getAcceleration(currPos);
        currPos += currVel * dt + 0.5 * acc * dt * dt;
        vec3 newAcc = getAcceleration(currPos);
        currVel += 0.5 * (acc + newAcc) * dt;

        // Black hole event horizon intersection test
        if (interceptBlackHole(currPos, SagA_rs)) { 
            transmission = 0.0;              // Complete absorption
            break; 
        }

        // Accretion disk intersection test (crossing Y=0 plane)
        if (prevPos.y * currPos.y < 0.0) {   // Sign change indicates plane crossing
            
            // Linear interpolation for precise intersection point
            float t = abs(prevPos.y) / (abs(prevPos.y) + abs(currPos.y));
            vec3 crossingPoint = mix(prevPos, currPos, t);

            // Calculate radial distance from black hole center
            float r = length(vec2(crossingPoint.x, crossingPoint.z));
            
            // Check if intersection is within disk boundaries
            if (r >= disk_r1 && r <= disk_r2) {
                if (length(currPos) > SagA_rs * 1.1) { // Avoid rendering when too close to black hole
                    
                    // Calculate texture coordinates with rotation animation
                    float hit_angle_raw = atan(crossingPoint.z, crossingPoint.x);
                    float rotation_speed = 0.05;
                    float hit_angle = hit_angle_raw + iTime * rotation_speed;
                    
                    // Normalize radial coordinate for texture mapping
                    float v_radial = (r - disk_r1) / (disk_r2 - disk_r1);
                    v_radial = clamp(v_radial, 0.0, 1.0);
                    
                    // Adjust texture coordinate to account for central hole
                    float texture_hole_norm = disk_r1 / disk_r2;
                    float v_texture = mix(texture_hole_norm, 1.0, v_radial);
                    
                    // Convert to final UV coordinates
                    vec2 uv = vec2(0.5 + v_texture * cos(hit_angle + PI) * 0.5, 
                                   0.5 + v_texture * sin(hit_angle + PI) * 0.5);
                    uv.y = 1.0 - uv.y;       // Flip Y-axis for texture coordinate system
                    
                    // Sample disk texture
                    vec4 texColor = texture(iDiskTexture, uv);

                    // Calculate alpha with smooth edge transitions
                    float alpha = smoothstep(0.0, 0.1, v_radial) * smoothstep(1.0, 0.9, v_radial);
                    alpha *= texColor.a;     // Apply texture alpha channel

                    // Accumulate color with transmission
                    accumulatedColor += texColor.rgb * alpha * transmission;
                    transmission *= (1.0 - alpha); // Reduce transmission based on opacity
                    
                    // Early termination for opaque paths
                    if (transmission < 0.01) break;
                }
            }
        }

        // Light source (star) intersection test
        if (interceptObject(currPos)) {
            // Calculate surface normal at intersection point
            vec3 N = normalize(currPos - hitCenter);
            
            // Calculate view direction
            vec3 V = normalize(iCamPos - currPos);
            
            // Simple diffuse lighting calculation
            float diff = max(dot(N, V), 0.0);
            vec3 shadedColor = objectColor.rgb * (0.2 + 0.8 * diff); // Ambient + diffuse
            
            // Accumulate shaded color with current transmission
            accumulatedColor += shadedColor * transmission;
            transmission = 0.0;              // Light sources are opaque
            break; 
        }
    }
    
    // Output final fragment color
    FragColor = vec4(accumulatedColor, 1.0);
}
