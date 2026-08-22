import type { Metadata } from 'next';
import { Instrument_Sans, Newsreader } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const instrument = Instrument_Sans({ variable: '--font-instrument', subsets: ['latin'] });
const newsreader = Newsreader({ variable: '--font-newsreader', subsets: ['latin'], style: ['normal', 'italic'] });

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? 'http://localhost:3000'),
  title: 'Atlas — Private, cited answers from your documents',
  description: 'A private RAG workspace that turns your documents into verifiable, cited answers.',
  openGraph: {
    title: 'Atlas — Private knowledge. Verifiable answers.',
    description: 'A private RAG workspace that turns your documents into verifiable, cited answers.',
    images: [{ url: '/og.png', width: 1200, height: 630, alt: 'Atlas — Private knowledge. Verifiable answers.' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Atlas — Private knowledge. Verifiable answers.',
    description: 'A private RAG workspace that turns your documents into verifiable, cited answers.',
    images: ['/og.png'],
  },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body className={`${instrument.variable} ${newsreader.variable}`}><Providers>{children}</Providers></body></html>;
}
