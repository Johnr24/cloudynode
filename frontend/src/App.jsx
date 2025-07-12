import React, { useCallback } from 'react';
import ReactFlow, {
  useNodesState,
  useEdgesState,
  addEdge,
  MiniMap,
  Controls,
  Background,
} from 'reactflow';
import TextUpdaterNode from './TextUpdaterNode.jsx';

import 'reactflow/dist/style.css';

const nodeTypes = { textUpdater: TextUpdaterNode };

const initialNodes = [
  { id: '1', type: 'textUpdater', position: { x: 250, y: 50 }, data: { label: 'Email Node' }, className: 'email-node' },
  { id: '2', type: 'textUpdater', position: { x: 250, y: 150 }, data: { label: 'Project Folder Node' }, className: 'project-folder-node' },
];
const initialEdges = [{ id: 'e1-2', source: '1', target: '2' }];

let id = 3;
const getId = () => `${id++}`;

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    [setEdges],
  );

  const onAddNode = useCallback((type) => {
    const newNode = {
      id: getId(),
      type: 'textUpdater',
      position: {
        x: Math.random() * (window.innerWidth - 200),
        y: 50 + Math.random() * (window.innerHeight - 150),
      },
      data: { label: `${type === 'email' ? 'Email' : 'Project Folder'} Node` },
      className: `${type === 'email' ? 'email-node' : 'project-folder-node'}`,
    };
    setNodes((nds) => nds.concat(newNode));
  }, [setNodes]);

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 4 }}>
        <button onClick={() => onAddNode('email')}>Add Email Node</button>
        <button onClick={() => onAddNode('project-folder')} style={{ marginLeft: 5 }}>Add Project Folder Node</button>
      </div>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
      >
        <Controls />
        <MiniMap />
        <Background variant="dots" gap={12} size={1} />
      </ReactFlow>
    </div>
  );
}

export default App;
