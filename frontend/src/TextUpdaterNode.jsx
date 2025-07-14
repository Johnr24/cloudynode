import { useCallback, useState, useEffect, useRef } from 'react';
import { Handle, Position, useReactFlow } from 'reactflow';

function TextUpdaterNode({ id, data, projectTypes = [], downloads = {} }) {
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
    if (!isEditing) {
      setSuggestions([]);
      return;
    }

    const handler = setTimeout(() => {
      if (!label) {
        setSuggestions([]);
        return;
      }
      setLoading(true);

      if (data.nodeType === 'project-folder') {
        const typesQuery = projectTypes.length > 0 ? `&types=${projectTypes.join('&types=')}` : '';
        fetch(`http://localhost:8000/projects/discover?name=${encodeURIComponent(label)}${typesQuery}`)
          .then(res => res.json())
          .then(data => {
            setSuggestions(data);
            setLoading(false);
          })
          .catch(() => setLoading(false));
      } else if (data.nodeType === 'email') {
        const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        // Only scan if the original label was an email, not a URL
        if (emailPattern.test(data.label)) {
          const params = new URLSearchParams();
          params.append('sender_emails', data.label);
          fetch(`http://localhost:8000/scan-emails?${params.toString()}`)
            .then(res => res.json())
            .then(data => {
              // Unify suggestion format
              setSuggestions(data.links ? data.links.map(link => ({ name: `${link.url} (from: ${link.sender})`, value: link.url, path: link.url })) : []);
              setLoading(false);
            })
            .catch(() => setLoading(false));
        } else {
          setLoading(false);
        }
      }
    }, 300);

    return () => {
      clearTimeout(handler);
    };
  }, [label, data.nodeType, data.label, isEditing, projectTypes]);

  const handleSelectSuggestion = (suggestion) => {
    setNodes((nodes) =>
      nodes.map((node) => {
        if (node.id === id) {
          if (data.nodeType === 'project-folder') {
            node.data = { ...node.data, label: suggestion.name, path: suggestion.path };
          } else { // email node
            node.data = { ...node.data, label: suggestion.value };
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
            {(data.nodeType === 'project-folder' || data.nodeType === 'email') && (
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
            {data.nodeType === 'email' && downloads[data.label] && (
              <div style={{ fontSize: '10px', color: downloads[data.label].status === 'failed' ? 'red' : 'gray' }}>
                Status: {downloads[data.label].message || downloads[data.label].status}
              </div>
            )}
          </div>
        )}
      </div>
      {data.nodeType === 'email' && <Handle type="source" position={Position.Bottom} />}
    </>
  );
}

export default TextUpdaterNode;
