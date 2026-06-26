import { vi, describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ExportFormats from '@/sections/ExportFormats';

vi.mock('@/hooks/useAPI', () => ({
  getExportFormats: vi.fn().mockResolvedValue([
    { id: 'qif', name: 'QIF', icon: 'FileText', color: '#C9A96E', status: 'Available', description: 'Quicken Interchange Format' },
    { id: 'csv', name: 'CSV', icon: 'Table', color: '#4ADE80', status: 'Available', description: 'Spreadsheet format' },
  ]),
  getProcessedFiles: vi.fn().mockResolvedValue([
    { file_id: 'f1', status: 'completed', filename: 'stmt.pdf' },
  ]),
}));

describe('ExportFormats', () => {
  it('renders available formats when statements are processed', async () => {
    render(
      <MemoryRouter>
        <ExportFormats />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText('QIF')).toBeInTheDocument());
    expect(screen.getByText('CSV')).toBeInTheDocument();
  });
});
