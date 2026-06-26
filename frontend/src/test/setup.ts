import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// Mock fetch globally for component tests that do not use the API hook.
globalThis.fetch = vi.fn();

// Provide matchMedia for gsap/ScrollTrigger in jsdom.
Object.defineProperty(globalThis, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});
