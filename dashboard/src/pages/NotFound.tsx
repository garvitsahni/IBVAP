import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '@/components/ui/Button';

export function NotFound() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="flex min-h-screen flex-col items-center justify-center bg-bg text-center"
    >
      <h1 className="text-4xl font-bold text-text-primary">Page not found</h1>
      <p className="mt-2 text-sm text-text-secondary">
        The screen you're looking for doesn't exist or may have moved.
      </p>
      <Link to="/dashboard">
        <Button className="mt-6">Back to dashboard</Button>
      </Link>
    </motion.div>
  );
}
