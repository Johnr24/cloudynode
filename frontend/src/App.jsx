import React, { useCallback, useEffect, useState, useMemo, useRef } from 'react';
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

let id = 1;
const getId = () => `${id++}`;

function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [isLoaded, setIsLoaded] = useState(false);
  const [projectTypes, setProjectTypes] = useState(['livework', 'turbosort']);
  const [downloads, setDownloads] = useState({});
  const ws = useRef(null);
  const clientId = useMemo(() => `client-${Math.random().toString(36).substr(2, 9)}`, []);
  // Parse backend host to handle both host:port and full URL formats
  const getBackendConfig = () => {
    const backendHost = import.meta.env.VITE_BACKEND_HOST || `${window.location.hostname}:2155`;

    // If it already includes protocol, parse it
    if (backendHost.startsWith('http://') || backendHost.startsWith('https://')) {
      const url = new URL(backendHost);
      return {
        httpUrl: backendHost,
        wsUrl: backendHost.replace(/^http/, 'ws'),
        host: url.host,
      };
    }

    // Otherwise, assume it's just host:port
    return {
      httpUrl: `http://${backendHost}`,
      wsUrl: `ws://${backendHost}`,
      host: backendHost,
    };
  };
  
  const backendConfig = useMemo(() => getBackendConfig(), []);

  const nodeTypes = useMemo(() => ({
    textUpdater: (props) => <TextUpdaterNode {...props} projectTypes={projectTypes} backendConfig={backendConfig} />
  }), [projectTypes, backendConfig]);

  useEffect(() => {
    let connectInterval = null;

    const connect = () => {
      ws.current = new WebSocket(`${backendConfig.wsUrl}/ws/progress/${clientId}`);

      ws.current.onopen = () => {
        console.log("WebSocket connected");
        if (connectInterval) {
          clearInterval(connectInterval);
          connectInterval = null;
        }
      };

      ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setDownloads(prev => ({
          ...prev,
          [data.url]: data,
        }));
      };

      ws.current.onclose = () => {
        console.log("WebSocket disconnected. Attempting to reconnect...");
        if (!connectInterval) {
          connectInterval = setInterval(() => {
            connect();
          }, 3000);
        }
      };

      ws.current.onerror = (err) => {
        console.error("WebSocket error:", err);
        ws.current.close();
      };
    };

    connect();

    return () => {
      if (connectInterval) {
        clearInterval(connectInterval);
      }
      if (ws.current) {
        // Prevent reconnect on component unmount
        ws.current.onclose = () => {};
        ws.current.close();
      }
    };
  }, [clientId, backendConfig.wsUrl]);

  useEffect(() => {
    fetch(`${backendConfig.httpUrl}/graph`)
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
    fetch(`${backendConfig.httpUrl}/graph`, {
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

  const handleProjectTypeChange = (e) => {
    const { name, checked } = e.target;
    setProjectTypes(prev => {
      if (checked) {
        return [...prev, name];
      } else {
        return prev.filter(t => t !== name);
      }
    });
  };

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
      <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 4, background: 'rgba(255, 255, 255, 0.8)', padding: 10, borderRadius: 5 }}>
        <button onClick={() => onAddNode('email')}>Add Email Node</button>
        <button onClick={() => onAddNode('project-folder')} style={{ marginLeft: 5 }}>Add Project Folder Node</button>
        <div style={{ marginTop: 5 }}>
          <span>Project Types:</span>
          <label style={{ marginLeft: 5 }}>
            <input
              type="checkbox"
              name="livework"
              checked={projectTypes.includes('livework')}
              onChange={handleProjectTypeChange}
            />
            Livework
          </label>
          <label style={{ marginLeft: 5 }}>
            <input
              type="checkbox"
              name="turbosort"
              checked={projectTypes.includes('turbosort')}
              onChange={handleProjectTypeChange}
            />
            Turbosort
          </label>
        </div>
      </div>
      <div style={{ position: 'absolute', top: 10, right: 10, zIndex: 4, background: 'rgba(255, 255, 255, 0.8)', padding: 10, borderRadius: 5, width: '300px', maxHeight: '50vh', overflowY: 'auto' }}>
        <h4>Downloads</h4>
        {Object.keys(downloads).length === 0 ? (
          <div style={{ fontSize: '12px', color: 'gray' }}>No active downloads.</div>
        ) : (
          Object.values(downloads).map(d => (
            <div key={d.url} style={{ fontSize: '12px', marginBottom: '5px', borderBottom: '1px solid #eee', paddingBottom: '5px' }}>
              <div style={{ wordBreak: 'break-all' }}><strong>URL:</strong> {d.url}</div>
              <div><strong>Status:</strong> {d.message || d.status}</div>
            </div>
          ))
        )}
      </div>
      <ReactFlow
        data-testid="react-flow-wrapper"
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
