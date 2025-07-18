import '@testing-library/jest-dom/vitest';
import { vi, beforeEach } from 'vitest';

// Mock ResizeObserver for React Flow
const ResizeObserverMock = vi.fn(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));
vi.stubGlobal('ResizeObserver', ResizeObserverMock);

// Mock WebSocket which is used in App.jsx
beforeEach(() => {
  global.WebSocket = vi.fn(() => ({
    onopen: vi.fn(),
    onmessage: vi.fn(),
    onclose: vi.fn(),
    onerror: vi.fn(),
    close: vi.fn(),
    send: vi.fn(),
  }));
});
