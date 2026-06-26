import { vi, describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import OFXUpload from '@/components/upload/OFXUpload';

vi.mock('@/hooks/useAPI', () => ({
  getAccounts: vi.fn().mockResolvedValue([
    { id: 1, name: 'Checking', type: 'checking' },
    { id: 2, name: 'Credit Card', account_type: 'credit_card' },
  ]),
  uploadOFX: vi.fn().mockResolvedValue({
    statement_id: 5,
    account_id: 1,
    account_name: 'Checking',
    transactions_count: 3,
    duplicates_skipped: 0,
    period_start: '2026-01-01',
    period_end: '2026-01-31',
  }),
}));

describe('OFXUpload', () => {
  it('renders upload area and accepts an OFX file', async () => {
    const { container } = render(
      <MemoryRouter>
        <OFXUpload />
      </MemoryRouter>
    );
    expect(screen.getByText('OFX / QFX Import')).toBeInTheDocument();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    if (!input) throw new Error('file input not found');
    const file = new File(['<OFX></SGML>'], 'statement.ofx', { type: 'application/x-ofx' });
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(screen.getByText(/Import statement.ofx/i)).toBeInTheDocument());
  });
});
