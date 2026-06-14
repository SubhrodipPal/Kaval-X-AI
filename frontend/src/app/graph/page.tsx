"use client";
import { useState, useMemo, useRef, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html, Text } from "@react-three/drei";
import * as THREE from "three";

// ─── Mock Graph Data ───
const genGraph = () => {
  const nodes: { id: string; x: number; y: number; z: number; risk: number; bank: string; isMule: boolean; cluster?: string }[] = [];
  const edges: { src: number; dst: number; amount: number }[] = [];
  const banks = ["SBIN", "HDFC", "ICIC", "AXIS", "KOTK"];

  for (let i = 0; i < 60; i++) {
    const isMule = Math.random() < 0.1;
    nodes.push({
      id: `acc_${i.toString().padStart(4, "0")}`,
      x: (Math.random() - 0.5) * 20,
      y: (Math.random() - 0.5) * 20,
      z: (Math.random() - 0.5) * 20,
      risk: isMule ? 0.7 + Math.random() * 0.3 : Math.random() * 0.6,
      bank: banks[i % banks.length],
      isMule,
      cluster: isMule ? `cluster_${Math.floor(i / 5)}` : undefined,
    });
  }
  for (let i = 0; i < 120; i++) {
    const src = Math.floor(Math.random() * nodes.length);
    let dst = Math.floor(Math.random() * nodes.length);
    if (dst === src) dst = (src + 1) % nodes.length;
    edges.push({ src, dst, amount: Math.floor(Math.random() * 500000) + 1000 });
  }
  return { nodes, edges };
};

// ─── 3D Node Component ───
function GraphNode({ position, risk, isMule, selected, onClick }: {
  position: [number, number, number]; risk: number; isMule: boolean;
  selected: boolean; onClick: () => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const color = risk > 0.7 ? "#FF3CAC" : risk > 0.4 ? "#FFD700" : "#00FFD1";

  useFrame((_, delta) => {
    if (meshRef.current) {
      if (selected) {
        meshRef.current.scale.setScalar(1.5 + Math.sin(Date.now() / 300) * 0.2);
      } else {
        meshRef.current.scale.lerp(new THREE.Vector3(1, 1, 1), delta * 5);
      }
    }
  });

  return (
    <mesh ref={meshRef} position={position} onClick={onClick}>
      <sphereGeometry args={[isMule ? 0.35 : 0.2, 16, 16]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={selected ? 0.8 : 0.3} transparent opacity={0.9} />
    </mesh>
  );
}

// ─── 3D Edge Component ───
function GraphEdge({ start, end }: { start: [number, number, number]; end: [number, number, number] }) {
  const ref = useRef<THREE.Group>(null);
  const geom = useMemo(() => {
    const points = [new THREE.Vector3(...start), new THREE.Vector3(...end)];
    const g = new THREE.BufferGeometry().setFromPoints(points);
    return g;
  }, [start, end]);
  const mat = useMemo(() => new THREE.LineBasicMaterial({ color: "#0F2035", transparent: true, opacity: 0.4 }), []);
  const lineObj = useMemo(() => new THREE.Line(geom, mat), [geom, mat]);
  return <primitive object={lineObj} />;
}

// ─── Scene ───
function Scene({ graph, selectedNode, onSelectNode, riskFilter }: {
  graph: ReturnType<typeof genGraph>; selectedNode: number | null;
  onSelectNode: (i: number) => void; riskFilter: number;
}) {
  return (
    <>
      <ambientLight intensity={0.3} />
      <pointLight position={[10, 10, 10]} intensity={1} color="#00FFD1" />
      <pointLight position={[-10, -10, -10]} intensity={0.5} color="#7B61FF" />

      {graph.edges.map((e, i) => {
        const s = graph.nodes[e.src];
        const d = graph.nodes[e.dst];
        if (s.risk < riskFilter && d.risk < riskFilter) return null;
        return <GraphEdge key={i} start={[s.x, s.y, s.z]} end={[d.x, d.y, d.z]} />;
      })}

      {graph.nodes.map((n, i) => {
        if (n.risk < riskFilter) return null;
        return (
          <GraphNode key={i} position={[n.x, n.y, n.z]} risk={n.risk}
            isMule={n.isMule} selected={selectedNode === i}
            onClick={() => onSelectNode(i)} />
        );
      })}

      <OrbitControls enableDamping dampingFactor={0.05} />
    </>
  );
}

export default function GraphPage() {
  const graph = useMemo(genGraph, []);
  const [selectedNode, setSelectedNode] = useState<number | null>(null);
  const [riskFilter, setRiskFilter] = useState(0);
  const node = selectedNode !== null ? graph.nodes[selectedNode] : null;

  return (
    <div className="h-[calc(100vh-8rem)] flex gap-4">
      {/* 3D Canvas */}
      <div className="flex-1 glass-card overflow-hidden relative">
        <Canvas camera={{ position: [0, 0, 30], fov: 60 }} style={{ background: "#03070F" }}>
          <Scene graph={graph} selectedNode={selectedNode}
            onSelectNode={setSelectedNode} riskFilter={riskFilter} />
        </Canvas>
        {/* Controls Overlay */}
        <div className="absolute bottom-4 left-4 right-4 flex items-center gap-4 bg-kx-surface/90 backdrop-blur-md rounded-lg p-3 border border-kx-border">
          <span className="text-xs text-kx-muted font-semibold">Risk Filter</span>
          <input type="range" min={0} max={100} value={riskFilter * 100}
            onChange={(e) => setRiskFilter(Number(e.target.value) / 100)}
            className="flex-1 accent-[#00FFD1] h-1" />
          <span className="text-xs font-mono text-kx-teal w-12 text-right">
            {(riskFilter * 100).toFixed(0)}%
          </span>
          <div className="flex gap-2 ml-4">
            <span className="text-[10px] flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#00FFD1]" /> Low</span>
            <span className="text-[10px] flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#FFD700]" /> Med</span>
            <span className="text-[10px] flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-[#FF3CAC]" /> High</span>
          </div>
        </div>
      </div>

      {/* Node Detail Sidebar */}
      <div className="w-72 glass-card p-5 overflow-y-auto shrink-0">
        <div className="text-sm font-bold text-kx-head mb-4">Node Details</div>
        {node ? (
          <div className="space-y-4">
            <div>
              <div className="text-xs text-kx-muted mb-1">Account ID</div>
              <div className="text-sm font-mono text-kx-teal">{node.id}</div>
            </div>
            <div>
              <div className="text-xs text-kx-muted mb-1">TGN Risk Score</div>
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 rounded-full bg-kx-border overflow-hidden">
                  <div className="h-full rounded-full transition-all"
                    style={{ width: `${node.risk * 100}%`, background: node.risk > 0.7 ? '#FF3CAC' : node.risk > 0.4 ? '#FFD700' : '#00FFD1' }} />
                </div>
                <span className="text-sm font-bold font-mono" style={{ color: node.risk > 0.7 ? '#FF3CAC' : node.risk > 0.4 ? '#FFD700' : '#00FFD1' }}>
                  {node.risk.toFixed(3)}
                </span>
              </div>
            </div>
            <div>
              <div className="text-xs text-kx-muted mb-1">Bank Code</div>
              <div className="text-sm font-mono">{node.bank}</div>
            </div>
            <div>
              <div className="text-xs text-kx-muted mb-1">Mule Account</div>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${node.isMule ? 'bg-[#FF3CAC20] text-[#FF3CAC]' : 'bg-[#00FFD120] text-[#00FFD1]'}`}>
                {node.isMule ? "YES — FLAGGED" : "NO"}
              </span>
            </div>
            {node.cluster && (
              <div>
                <div className="text-xs text-kx-muted mb-1">Cluster ID</div>
                <div className="text-sm font-mono text-kx-purple">{node.cluster}</div>
              </div>
            )}
            <div>
              <div className="text-xs text-kx-muted mb-1">Connected Edges</div>
              <div className="text-sm font-mono">
                {graph.edges.filter(e => e.src === selectedNode || e.dst === selectedNode).length}
              </div>
            </div>
            <hr className="border-kx-border" />
            <div className="text-[10px] text-kx-muted">Click a different node to inspect it. Use mouse to orbit/zoom the 3D graph.</div>
          </div>
        ) : (
          <div className="text-sm text-kx-muted text-center mt-8">Click a node to inspect</div>
        )}
      </div>
    </div>
  );
}
