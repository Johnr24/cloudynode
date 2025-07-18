import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import App from './App';

describe('App', () => {
  let fetchSpy;

  beforeEach(() => {
    // Mock fetch to return an empty graph
    fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      json: vi.fn().mockResolvedValue({ nodes: [], edges: [] }),
      ok: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders the ReactFlow component', async () => {
    render(<App />);
    expect(await screen.findByTestId('react-flow-wrapper')).toBeInTheDocument();
  });

  it('loads default nodes when fetch returns no data', async () => {
    render(<App />);
    // Wait for the component to finish loading data and setting up default nodes
    expect(await screen.findByText('Email Node')).toBeInTheDocument();
    expect(await screen.findByText('Project Folder Node')).toBeInTheDocument();
  });

  it('adds an email node when "Add Email Node" button is clicked', async () => {
    render(<App />);
    // Wait for initial load
    await screen.findByTestId('react-flow-wrapper');
    
    const addButton = screen.getByText('Add Email Node');
    fireEvent.click(addButton);

    // After clicking, a new node with "Email Node" should appear.
    // Since there's already one, we should find two.
    expect(await screen.findAllByText('Email Node')).toHaveLength(2);
  });

  it('adds a project folder node when "Add Project Folder Node" button is clicked', async () => {
    render(<App />);
    // Wait for initial load
    await screen.findByTestId('react-flow-wrapper');
    
    const addButton = screen.getByText('Add Project Folder Node');
    fireEvent.click(addButton);

    // After clicking, a new node with "Project Folder Node" should appear.
    // Since there's already one, we should find two.
    expect(await screen.findAllByText('Project Folder Node')).toHaveLength(2);
  });
});
