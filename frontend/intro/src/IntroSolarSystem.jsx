import React, { forwardRef, useEffect, useMemo, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

const DURATION_MS = 8200;
const MAX_PCT = 99;
const STEP_MS = 42;

function makeGlowTexture() {
  const sz = 256;
  const cvs = document.createElement('canvas');
  cvs.width = cvs.height = sz;
  const ctx = cvs.getContext('2d');
  const g = ctx.createRadialGradient(sz / 2, sz / 2, 0, sz / 2, sz / 2, sz / 2);
  g.addColorStop(0.0, 'rgba(255,220,130,0.96)');
  g.addColorStop(0.2, 'rgba(255,170,60,0.55)');
  g.addColorStop(0.55, 'rgba(255,120,30,0.16)');
  g.addColorStop(1.0, 'rgba(255,100,20,0.00)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, sz, sz);
  const tex = new THREE.CanvasTexture(cvs);
  tex.minFilter = THREE.LinearFilter;
  tex.magFilter = THREE.LinearFilter;
  return tex;
}

const StarField = forwardRef(function StarField(props, ref) {
  const stars = useMemo(() => {
    const count = 3000;
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      pos[i * 3] = (Math.random() - 0.5) * 280;
      pos[i * 3 + 1] = (Math.random() - 0.5) * 140;
      pos[i * 3 + 2] = -Math.random() * 260;
    }
    return pos;
  }, []);

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(stars, 3));
    return g;
  }, [stars]);

  return (
    <points ref={ref} geometry={geometry}>
      <pointsMaterial color={0xbcdcff} size={0.24} sizeAttenuation />
    </points>
  );
});

function RiggedSolarScene({ onPct, onDone }) {
  const { camera } = useThree();
  const startTimeRef = useRef(performance.now());
  const doneRef = useRef(false);
  const lastPctRef = useRef(1);

  const sunRef = useRef();
  const earthOrbitRef = useRef();
  const earthRef = useRef();
  const cloudsRef = useRef();
  const starFieldRef = useRef();
  const [glowTex] = useState(() => makeGlowTexture());

  useFrame((state) => {
    const now = performance.now();
    const elapsed = now - startTimeRef.current;
    const t = Math.min(1, elapsed / DURATION_MS);

    // rotations
    if (sunRef.current) sunRef.current.rotation.y += 0.003;
    if (earthOrbitRef.current) earthOrbitRef.current.rotation.y += 0.0022;
    if (earthRef.current) earthRef.current.rotation.y += 0.007;
    if (cloudsRef.current) cloudsRef.current.rotation.y += 0.0085;
    if (starFieldRef.current) starFieldRef.current.rotation.y += 0.00006;

    // camera follow (goal position based on earth world position)
    if (earthRef.current) {
      const earthWorld = new THREE.Vector3();
      earthRef.current.getWorldPosition(earthWorld);

      const zt = Math.max(0, (t - 0.18) / 0.82);
      const ease = zt * zt * (3 - 2 * zt);
      const goal = new THREE.Vector3(
        earthWorld.x + 1.1,
        earthWorld.y + 0.7,
        earthWorld.z + 3.2,
      );

      camera.position.lerp(goal, 0.024 + ease * 0.11);
      camera.lookAt(earthWorld.x, earthWorld.y, earthWorld.z);
    }

    const nextPct = Math.min(MAX_PCT, 1 + Math.floor(elapsed / STEP_MS));
    if (nextPct !== lastPctRef.current) {
      lastPctRef.current = nextPct;
      onPct?.(nextPct);
    }

    if (t >= 1 && !doneRef.current) {
      doneRef.current = true;
      onDone?.();
    }
  });

  useEffect(() => {
    // Safety valve: never let the intro block the UI.
    const timeout = setTimeout(() => {
      if (!doneRef.current) {
        doneRef.current = true;
        onDone?.();
      }
    }, DURATION_MS + 1500);
    return () => clearTimeout(timeout);
  }, [onDone]);

  return (
    <>
      <ambientLight intensity={1.2} color={0x304060} />
      <hemisphereLight intensity={0.7} color={0x6aadff} groundColor={0x0b1020} />
      <directionalLight position={[8, 6, 18]} intensity={0.6} color={0xffffff} />

      <StarField ref={starFieldRef} />

      <mesh ref={sunRef}>
        <sphereGeometry args={[2.4, 48, 48]} />
        <meshBasicMaterial color={0xffc857} />
        <sprite scale={[9.6, 9.6, 1]}>
          <spriteMaterial
            map={glowTex}
            transparent
            opacity={0.9}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </sprite>
      </mesh>

      <pointLight distance={240} intensity={3.5} color={0xfff2c8} />

      <group ref={earthOrbitRef}>
        <mesh ref={earthRef} position={[11.5, -0.2, 0]}>
          <sphereGeometry args={[1.1, 64, 64]} />
          <meshPhongMaterial
            color={0x2a7bd6}
            emissive={new THREE.Color(0x072040)}
            emissiveIntensity={0.3}
            shininess={18}
            specular={new THREE.Color(0x1a3a55)}
          />
          <mesh ref={cloudsRef} position={[0, 0, 0]}>
            <sphereGeometry args={[1.14, 48, 48]} />
            <meshPhongMaterial transparent opacity={0} depthWrite={false} />
          </mesh>
          <mesh position={[0, 0, 0]}>
            <sphereGeometry args={[1.19, 48, 48]} />
            <meshPhongMaterial
              color={0x66bbff}
              transparent
              opacity={0.22}
              side={THREE.DoubleSide}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </mesh>
      </group>

      {/* Simple background planets */}
      <mesh position={[17.5, 2.6, -4]}>
        <sphereGeometry args={[0.38, 24, 24]} />
        <meshPhongMaterial color={0xc96f4b} emissive={new THREE.Color(0x3a1600)} emissiveIntensity={0.3} />
      </mesh>
      <mesh position={[-16, 3.4, -10]}>
        <sphereGeometry args={[0.85, 32, 32]} />
        <meshPhongMaterial color={0xbe9f7b} emissive={new THREE.Color(0x261900)} emissiveIntensity={0.2} />
      </mesh>

      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <ringGeometry args={[11.4, 11.5, 160]} />
        <meshBasicMaterial
          color={0x3d6899}
          transparent
          opacity={0.28}
          side={THREE.DoubleSide}
        />
      </mesh>
    </>
  );
}

export function IntroSolarSystem({ onComplete }) {
  const [pct, setPct] = useState(1);

  useEffect(() => {
    setPct(1);
  }, []);

  return (
    <div className="intro-root">
      <Canvas
        gl={{ alpha: true, antialias: true }}
        dpr={Math.min(window.devicePixelRatio || 1, 2)}
        camera={{ fov: 48, position: [0, 2, 26] }}
      >
        <RiggedSolarScene
          onPct={(v) => setPct(v)}
          onDone={() => onComplete?.()}
        />
      </Canvas>

      <div className="introHud introHud-react">
        <div className="introText">SOLARIS/GRID INITIALIZING...</div>
        <button
          id="skipIntro"
          type="button"
          className="introSkipBtn"
          onClick={() => onComplete?.()}
        >
          Skip intro
        </button>
      </div>

      <div className="introLoader">{pct}%</div>
    </div>
  );
}

