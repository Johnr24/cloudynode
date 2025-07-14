import { useCallback, useState, useEffect, useRef } from 'react';
import { Handle, Position, useReactFlow } from 'reactflow';

function TextUpdaterNode({ id, data, projectTypes = [] }) {
  const { setNodes } = useReactFlow();
  const [isEditing, setIsEditing] = useState(false);
  const [label, setLabel] = useState(data.label);
  const inputRef = useRef(null);

  // For project folder autocomplete
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleDoubleClick = useCallback(() => {
    setLabel(data.label);
    setIsEditing(true);
  }, [data.label]);

  const handleBlur = useCallback(() => {
    setIsEditing(false);
    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.id === id) {
          node.data = { ...node.data, label };
        }
        return node;
      })
    );
    setSuggestions([]); // Clear suggestions on blur
  }, [id, label, setNodes]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleBlur();
      }
    },
    [handleBlur]
  );

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Debounced search for suggestions
  useEffect(() => {
    if (!isEditing || data.nodeType !== 'project-folder') {
      setSuggestions([]);
      return;
    }

    const handler = setTimeout(() => {
      if (!label) {
        setSuggestions([]);
        return;
      }
      setLoading(true);

      const typesQuery = projectTypes.length > 0 ? `&types=${projectTypes.join('&types=')}` : '';
      fetch(`http://localhost:8000/projects/discover?name=${encodeURIComponent(label)}${typesQuery}`)
        .then(res => res.json())
        .then(data => {
          setSuggestions(data);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }, 300);

    return () => {
      clearTimeout(handler);
    };
  }, [label, data.nodeType, isEditing, projectTypes]);

  const handleSelectSuggestion = (suggestion) => {
    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.id === id) {
          if (data.nodeType === 'project-folder') {
            node.data = { ...node.data, label: suggestion.name, path: suggestion.path, projectType: suggestion.type };
          }
        }
        return node;
      })
    );
    setIsEditing(false);
    setSuggestions([]);
  };

  return (
    <>
      {data.nodeType === 'project-folder' && <Handle type="target" position={Position.Top} />}
      <div onDoubleClick={handleDoubleClick}>
        {isEditing ? (
          <div className="nodrag">
            <textarea
              ref={inputRef}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
            />
            {data.nodeType === 'project-folder' && (
              <>
                {loading && <div style={{ fontSize: '10px', color: 'gray' }}>Loading...</div>}
                {suggestions.length > 0 && (
                  <ul style={{ position: 'absolute', listStyle: 'none', padding: 0, margin: 0, background: 'white', border: '1px solid #ccc', zIndex: 10, width: '200px' }}>
                    {suggestions.map(suggestion => (
                      <li key={suggestion.path} onMouseDown={() => handleSelectSuggestion(suggestion)} style={{ padding: '2px 4px', cursor: 'pointer', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {suggestion.name} {suggestion.type ? `(${suggestion.type})` : ''}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        ) : (
          <div>
            <div>{data.label}</div>
          </div>
        )}
      </div>
      {data.nodeType === 'email' && <Handle type="source" position={Position.Bottom} />}
    </>
  );
}

export default TextUpdaterNode;
