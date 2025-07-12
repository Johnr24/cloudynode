import React, { useCallback, useEffect, useState } from 'react';
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

let id = 1;
const getId = () => `${id++}`;

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    fetch('http://localhost:8000/graph')
      .then((res) => res.json())
      .then((data) => {
        const hasData = data.nodes && data.nodes.length > 0;
        if (hasData) {
          const patchedNodes = data.nodes.map(node => {
            if (!node.data.nodeType) {
              node.data.nodeType = node.className.includes('email-node') ? 'email' : 'project-folder';
            }
            return node;
          });
          setNodes(patchedNodes);
          setEdges(data.edges || []);
          const maxId = data.nodes.reduce((max, node) => Math.max(max, parseInt(node.id, 10) || 0), 0);
          id = maxId + 1;
        } else {
          const defaultNodes = [
            { id: '1', type: 'textUpdater', position: { x: 250, y: 50 }, data: { label: 'Email Node', nodeType: 'email' }, className: 'email-node' },
            { id: '2', type: 'textUpdater', position: { x: 250, y: 150 }, data: { label: 'Project Folder Node', nodeType: 'project-folder' }, className: 'project-folder-node' },
          ];
          const defaultEdges = [{ id: 'e1-2', source: '1', target: '2' }];
          setNodes(defaultNodes);
          setEdges(defaultEdges);
          id = 3;
        }
        setIsLoaded(true);
      });
  }, [setNodes, setEdges]);

  useEffect(() => {
    if (!isLoaded) {
      return;
    }
    const graphState = { nodes, edges };
    fetch('http://localhost:8000/graph', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(graphState),
    });
  }, [nodes, edges, isLoaded]);

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
      data: { label: `${type === 'email' ? 'Email' : 'Project Folder'} Node`, nodeType: type },
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
