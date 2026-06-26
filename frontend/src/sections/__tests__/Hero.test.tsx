import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Hero from '@/sections/Hero';

describe('Hero', () => {
  it('shows updated parser branding and OFX support', () => {
    render(
      <MemoryRouter>
        <Hero />
      </MemoryRouter>
    );
    expect(screen.getByText('16+')).toBeInTheDocument();
    expect(screen.getByText('Supported Institutions')).toBeInTheDocument();
    expect(screen.getByText('PDF/CSV/OFX')).toBeInTheDocument();
  });
});
