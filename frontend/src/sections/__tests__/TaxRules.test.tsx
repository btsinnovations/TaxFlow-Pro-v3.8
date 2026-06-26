import { vi, describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import TaxRules from '@/sections/TaxRules';

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: { id: 1, tenant_id: 1 } }),
}));

vi.mock('@/hooks/useAPI', () => ({
  searchTaxRules: vi.fn().mockResolvedValue([
    {
      id: 1,
      name: 'Office Supplies',
      pattern: 'STAPLES|OFFICE DEPOT',
      form: 'Schedule C',
      line: 'line_18',
      gl_account_id: 10,
      priority: 100,
      enabled: true,
      category: 'Deductions',
    },
  ]),
}));

describe('TaxRules', () => {
  it('renders the search UI and rule list', async () => {
    render(
      <MemoryRouter>
        <TaxRules />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText('Office Supplies')).toBeInTheDocument());
    expect(screen.getByText('Schedule C')).toBeInTheDocument();
    expect(screen.getByText('Tax Rules Engine')).toBeInTheDocument();
  });
});
