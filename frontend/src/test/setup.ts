import "@testing-library/jest-dom/vitest";
import { vi, afterAll, afterEach, beforeAll } from "vitest";
import { server } from "../mocks/server";

// Start MSW server before all tests, reset handlers after each, clean up after all.
beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

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
