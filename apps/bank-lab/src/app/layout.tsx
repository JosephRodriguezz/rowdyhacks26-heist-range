import type {Metadata} from 'next';
import './globals.css';
export const metadata: Metadata = {title: 'Rowdy Bank', description: 'A fictional bank for the RowdyHacks security challenge.'};
export default function Layout({children}: {children: React.ReactNode}) {
  return <html lang="en"><body>{children}</body></html>;
}
