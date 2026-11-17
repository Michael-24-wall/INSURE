import { Component, Suspense, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, OrbitControls, RoundedBox } from "@react-three/drei";
import { INSPECTION_ZONES } from "../lib/constants";

const severityColors = {
  minor: "#facc15",
  moderate: "#fb923c",
  severe: "#ef4444",
};

class SceneErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

function Wheel({ position }) {
  return (
    <group position={position} rotation={[Math.PI / 2, 0, 0]}>
      <mesh castShadow>
        <cylinderGeometry args={[0.44, 0.44, 0.26, 28]} />
        <meshStandardMaterial color="#0a0f12" roughness={0.8} />
      </mesh>
      <mesh position={[0, 0.14, 0]}>
        <cylinderGeometry args={[0.24, 0.24, 0.02, 24]} />
        <meshStandardMaterial color="#b8c4c9" metalness={0.8} roughness={0.3} />
      </mesh>
      <mesh position={[0, -0.14, 0]}>
        <cylinderGeometry args={[0.24, 0.24, 0.02, 24]} />
        <meshStandardMaterial color="#b8c4c9" metalness={0.8} roughness={0.3} />
      </mesh>
    </group>
  );
}

function Car() {
  return (
    <group position={[0, 0.02, 0]}>
      <RoundedBox args={[4.2, 0.7, 1.85]} radius={0.22} smoothness={5} position={[0, 0.62, 0]} castShadow receiveShadow>
        <meshStandardMaterial color="#0f8a6d" metalness={0.65} roughness={0.28} />
      </RoundedBox>

      <RoundedBox args={[2.45, 0.66, 1.66]} radius={0.2} smoothness={5} position={[-0.25, 1.18, 0]} castShadow>
        <meshStandardMaterial color="#0b7660" metalness={0.7} roughness={0.25} />
      </RoundedBox>

      <mesh position={[0.78, 1.23, 0]} rotation={[0, 0, -0.12]}>
        <boxGeometry args={[0.55, 0.5, 1.55]} />
        <meshStandardMaterial color="#07161d" metalness={0.35} roughness={0.15} />
      </mesh>
      <mesh position={[-0.92, 1.23, 0]} rotation={[0, 0, 0.1]}>
        <boxGeometry args={[0.5, 0.48, 1.55]} />
        <meshStandardMaterial color="#07161d" metalness={0.35} roughness={0.15} />
      </mesh>
      <mesh position={[-0.08, 1.34, 0.78]}>
        <boxGeometry args={[1.4, 0.32, 0.02]} />
        <meshStandardMaterial color="#0a1b22" metalness={0.4} roughness={0.2} />
      </mesh>
      <mesh position={[-0.08, 1.34, -0.78]}>
        <boxGeometry args={[1.4, 0.32, 0.02]} />
        <meshStandardMaterial color="#0a1b22" metalness={0.4} roughness={0.2} />
      </mesh>

      <mesh position={[2.05, 0.72, 0.56]}>
        <boxGeometry args={[0.12, 0.18, 0.42]} />
        <meshStandardMaterial color="#d0f45c" emissive="#a3c42c" emissiveIntensity={0.8} />
      </mesh>
      <mesh position={[2.05, 0.72, -0.56]}>
        <boxGeometry args={[0.12, 0.18, 0.42]} />
        <meshStandardMaterial color="#d0f45c" emissive="#a3c42c" emissiveIntensity={0.8} />
      </mesh>
      <mesh position={[-2.05, 0.72, 0.56]}>
        <boxGeometry args={[0.1, 0.16, 0.38]} />
        <meshStandardMaterial color="#ef4444" emissive="#991b1b" emissiveIntensity={0.6} />
      </mesh>
      <mesh position={[-2.05, 0.72, -0.56]}>
        <boxGeometry args={[0.1, 0.16, 0.38]} />
        <meshStandardMaterial color="#ef4444" emissive="#991b1b" emissiveIntensity={0.6} />
      </mesh>

      <mesh position={[2.12, 0.42, 0]}>
        <boxGeometry args={[0.16, 0.18, 1.32]} />
        <meshStandardMaterial color="#0a1519" metalness={0.7} roughness={0.3} />
      </mesh>
      <mesh position={[-2.12, 0.42, 0]}>
        <boxGeometry args={[0.16, 0.18, 1.32]} />
        <meshStandardMaterial color="#0a1519" metalness={0.7} roughness={0.3} />
      </mesh>

      <Wheel position={[1.38, 0.4, 0.98]} />
      <Wheel position={[1.38, 0.4, -0.98]} />
      <Wheel position={[-1.38, 0.4, 0.98]} />
      <Wheel position={[-1.38, 0.4, -0.98]} />
    </group>
  );
}

function DamageMarker({ zone, damage, selected, onZone }) {
  const [hovered, setHovered] = useState(false);
  const color = severityColors[damage?.severity] || "#d0f45c";
  return (
    <group position={zone.position}>
      <mesh
        scale={selected ? 1.25 : hovered ? 1.15 : 1}
        onClick={(event) => {
          event.stopPropagation();
          onZone?.(zone.key);
        }}
        onPointerOver={(event) => {
          event.stopPropagation();
          setHovered(true);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          setHovered(false);
          document.body.style.cursor = "auto";
        }}
      >
        <sphereGeometry args={[0.1, 16, 16]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.8} />
      </mesh>
      {(selected || hovered) && (
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.18, 0.24, 32]} />
          <meshBasicMaterial color={color} transparent opacity={0.8} side={2} />
        </mesh>
      )}
    </group>
  );
}

export function VehicleScene({ damages = [], onZone, selectedZone, className = "h-[420px]", interactive = true }) {
  const damageByZone = useMemo(() => {
    const map = {};
    damages.forEach((damage) => {
      if (!map[damage.zone] || damage.severity === "severe") map[damage.zone] = damage;
    });
    return map;
  }, [damages]);

  const visibleZones = interactive
    ? INSPECTION_ZONES
    : ["front_bumper", "bonnet", "windshield", "front_left_door", "rear_left_door", "roof", "rear_bumper", "left_front_wheel", "right_front_wheel"].map(
        (key) => INSPECTION_ZONES.find((zone) => zone.key === key)
      );

  return (
    <div className={`relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-ink-950 via-ink-900 to-[#083d36] ${className}`}>
      <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-center justify-between p-4">
        <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-white/55">
          360° vehicle view
        </span>
        {interactive && (
          <span className="rounded-full border border-lime-300/20 bg-lime-300/10 px-3 py-1 text-[10px] font-semibold text-lime-200">
            Tap a marker to record damage
          </span>
        )}
      </div>
      <SceneErrorBoundary
        fallback={
          <div className="flex h-full items-center justify-center px-8 text-center">
            <p className="max-w-sm text-sm leading-relaxed text-white/60">3D view is unavailable on this device. Use the zone list beside the inspection to record damage.</p>
          </div>
        }
      >
        <Suspense
          fallback={
            <div className="flex h-full items-center justify-center">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-lime-300 border-t-transparent" />
            </div>
          }
        >
          <Canvas shadows dpr={[1, 2]} camera={{ position: [5.2, 3.1, 5.6], fov: 36 }}>
            <color attach="background" args={["#07161d"]} />
            <fog attach="fog" args={["#07161d", 9, 17]} />
            <ambientLight intensity={0.7} />
            <directionalLight position={[5, 8, 5]} intensity={2.1} castShadow shadow-mapSize={[1024, 1024]} />
            <directionalLight position={[-4, 4, -4]} intensity={0.8} color="#67e8c2" />
            <spotLight position={[0, 7, 0]} angle={0.5} penumbra={1} intensity={1.2} color="#d0f45c" />

            <group position={[0, -0.1, 0]}>
              <Car />
              {visibleZones.filter(Boolean).map((zone) => (
                <DamageMarker
                  key={zone.key}
                  zone={zone}
                  damage={damageByZone[zone.key]}
                  selected={selectedZone === zone.key}
                  onZone={onZone}
                />
              ))}
              <ContactShadows position={[0, -0.12, 0]} opacity={0.55} scale={12} blur={2.6} far={4} color="#000000" />
              <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.14, 0]} receiveShadow>
                <circleGeometry args={[5.2, 64]} />
                <meshStandardMaterial color="#0a242c" roughness={0.9} metalness={0.1} />
              </mesh>
            </group>

            <OrbitControls
              enablePan={false}
              enableZoom={interactive}
              autoRotate
              autoRotateSpeed={0.75}
              minDistance={5}
              maxDistance={9}
              minPolarAngle={0.9}
              maxPolarAngle={1.45}
              target={[0, 0.8, 0]}
            />
          </Canvas>
        </Suspense>
      </SceneErrorBoundary>
      {interactive && (
        <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 flex items-center justify-center gap-4 p-4 text-[10px] font-medium text-white/55">
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-lime-300" /> Undamaged</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-400" /> Minor / moderate</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-red-500" /> Severe</span>
        </div>
      )}
    </div>
  );
}
