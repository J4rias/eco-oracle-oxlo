import { Box, Text, Stack } from '@mantine/core';
import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';

const STAGE_MAPPING: Record<string, { label: string, progress: number }> = {
  "input_validator": { label: "Initializing Geo-Spatial Validation...", progress: 15 },
  "satellite_fetcher": { label: "Acquiring Multi-Spectral Imagery...", progress: 35 },
  "vision_analyzer": { label: "Performing Neural Land Analysis...", progress: 60 },
  "legal_reasoner": { label: "Reasoning EUDR Compliance...", progress: 85 },
  "audit_finalizer": { label: "Finalizing Immutable Audit Record...", progress: 100 },
};

interface AnalysisLoaderProps {
  activeStage: string | null;
}

export function AnalysisLoader({ activeStage }: AnalysisLoaderProps) {
  const [displayProgress, setDisplayProgress] = useState(0);
  const [currentLabel, setCurrentLabel] = useState("Starting Analysis Pipeline...");

  useEffect(() => {
    if (activeStage && STAGE_MAPPING[activeStage]) {
      const { label, progress } = STAGE_MAPPING[activeStage];
      setCurrentLabel(label);
      setDisplayProgress(progress);
    }
  }, [activeStage]);

  return (
    <Stack gap="xl" align="center" justify="center" style={{ height: '300px', width: '100%', maxWidth: '600px', margin: '0 auto' }}>
      <Box w="100%" h={40} style={{ overflow: 'hidden', position: 'relative' }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={currentLabel}
            initial={{ opacity: 0, y: 15, filter: 'blur(10px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -15, filter: 'blur(10px)' }}
            transition={{ duration: 0.6, ease: "easeOut" }}
            style={{ width: '100%', textAlign: 'center' }}
          >
            <Text fw={700} size="xl" variant="gradient" gradient={{ from: 'teal', to: 'green', deg: 45 }}>
              {currentLabel}
            </Text>
          </motion.div>
        </AnimatePresence>
      </Box>

      <Box w="100%" h={12} bg="var(--mantine-color-dark-6)" style={{ borderRadius: '20px', position: 'relative', border: '1px solid var(--mantine-color-dark-4)' }}>
        <motion.div
          animate={{ width: `${displayProgress}%` }}
          transition={{ duration: 0.2, ease: "linear" }}
          style={{ 
            height: '100%', 
            borderRadius: '20px', 
            background: 'linear-gradient(90deg, #0ca678 0%, #20c997 100%)',
            boxShadow: '0 0 15px rgba(12, 166, 120, 0.4)',
            position: 'relative'
          }}
        >
          {/* Glowing front effect */}
          <motion.div 
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1.5, repeat: Infinity }}
            style={{
              position: 'absolute',
              right: 0,
              top: '-4px',
              height: '20px',
              width: '20px',
              background: '#fff',
              filter: 'blur(8px)',
              borderRadius: '50%',
              boxShadow: '0 0 10px #fff'
            }}
          />
        </motion.div>
      </Box>
      <Text size="xs" c="dimmed" fs="italic">Orchestrating autonomous geo-spatial audit...</Text>
    </Stack>
  );
}
