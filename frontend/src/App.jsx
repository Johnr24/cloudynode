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
  const [foundUrls, setFoundUrls] = useState([]);
  const [isScanning, setIsScanning] = useState(false);
  const [downloads, setDownloads] = useState({});
  const ws = useRef(null);
  const clientId = useMemo(() => `client-${Math.random().toString(36).substr(2, 9)}`, []);

  const handleScanEmails = useCallback(async (projectNodeId) => {
    setIsScanning(true);
    setFoundUrls([]);

    // Find connected email nodes
    const sourceEdges = edges.filter(edge => edge.target === projectNodeId);
    const sourceNodeIds = sourceEdges.map(edge => edge.source);
    const emailNodes = nodes.filter(node => sourceNodeIds.includes(node.id) && node.data.nodeType === 'email');
    const senderEmails = emailNodes.map(node => node.data.label);

    if (senderEmails.length === 0) {
        alert('No email nodes connected to this project folder.');
        setIsScanning(false);
        return;
    }

    try {
        const params = new URLSearchParams();
        senderEmails.forEach(email => params.append('sender_emails', email));
        const response = await fetch(`http://localhost:8000/scan-emails?${params.toString()}`);
        const data = await response.json();
        if (response.ok) {
            // Associate found URLs with the project folder they were scanned for
            setFoundUrls(data.urls.map(url => ({ url, projectNodeId })));
            if (data.urls.length === 0) {
                alert('No new WeTransfer links found.');
            }
        } else {
            alert(`Error: ${data.detail}`);
        }
    } catch (error) {
        alert(`Error scanning emails: ${error.message}`);
    }
    setIsScanning(false);
  }, [nodes, edges]);

  const handleDownload = useCallback((url, projectNodeId) => {
    if (!projectNodeId) {
        alert('Project folder not specified for download.');
        return;
    }
    setDownloads(prev => ({ ...prev, [url]: { status: 'starting' } }));
    fetch('http://localhost:8000/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, project_node_id: projectNodeId, client_id: clientId }),
    });
  }, [clientId]);

  const nodeTypes = useMemo(() => ({
    textUpdater: (props) => <TextUpdaterNode {...props} onScan={handleScanEmails} projectTypes={projectTypes} />
  }), [projectTypes, handleScanEmails]);

  useEffect(() => {
    ws.current = new WebSocket(`ws://localhost:8000/ws/progress/${clientId}`);
    ws.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        setDownloads(prev => ({
            ...prev,
            [data.url]: data,
        }));
    };
    return () => {
        if (ws.current) {
            ws.current.close();
        }
    };
  }, [clientId]);

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
        {isScanning && <div style={{ marginTop: 5 }}>Scanning...</div>}
        {foundUrls.length > 0 && (
          <div style={{ marginTop: 10, background: 'rgba(255, 255, 255, 0.9)', padding: 10, border: '1px solid #ccc', borderRadius: 5, maxHeight: '300px', overflowY: 'auto' }}>
              <h4>Found WeTransfer Links</h4>
              {foundUrls.map(({ url, projectNodeId }) => {
                  const downloadStatus = downloads[url];
                  const projectNode = nodes.find(n => n.id === projectNodeId);
                  return (
                      <div key={url} style={{ marginBottom: 5, padding: 5, border: '1px solid #eee', borderRadius: 3 }}>
                          <a href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '12px' }}>{url.substring(0, 40)}...</a>
                          <div style={{ fontSize: '12px' }}>To: {projectNode ? projectNode.data.label : 'Unknown Project'}</div>
                          <button
                              onClick={() => handleDownload(url, projectNodeId)}
                              style={{ marginLeft: 5 }}
                              disabled={!projectNodeId || (downloadStatus && downloadStatus.status !== 'skipped' && downloadStatus.status !== 'failed')}
                          >
                              Download
                          </button>
                          {downloadStatus && (
                              <div style={{ fontSize: '12px', marginLeft: 5, marginTop: 3, color: downloadStatus.status === 'failed' ? 'red' : 'inherit' }}>
                                  Status: {downloadStatus.message || downloadStatus.status}
                              </div>
                          )}
                      </div>
                  );
              })}
          </div>
        )}
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
