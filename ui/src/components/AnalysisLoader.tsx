import { Box, Text, Stack } from '@mantine/core';
import { motion, AnimatePresence } from 'framer-motion';
import { useState, useEffect } from 'react';

const STAGE_MAPPING: Record<string, { label: string, progress: number }> = {
  "input_validator": { label: "Validating Geo-Spatial Boundary...", progress: 10 },
  "satellite_fetcher": { label: "Acquiring Multi-Spectral Imagery...", progress: 30 },
  "vision_analyzer": { label: "Analyzing Vegetation Morphology...", progress: 55 },
  "legal_reasoner": { label: "Reasoning EUDR Compliance Verdict...", progress: 85 },
  "audit_finalizer": { label: "Sealing Immutable Audit Record...", progress: 100 },
};

const SUB_MAPPING: Record<string, string[]> = {
  "input_validator": [
    "Checking polygon geometry integrity...",
    "Verifying CRS (Coordinate Reference System)...",
    "Calculating total hectare footprint...",
  ],
  "satellite_fetcher": [
    "Contacting Sentinel-2 L2A constellation...",
    "Filtering cloud cover interference...",
    "Retrieving RGB and SWIR spectral bands...",
    "Normalizing pixel reflectance data...",
  ],
  "vision_analyzer": [
    "Running YOLOv9 neural inference...",
    "Detecting forest canopy variations...",
    "Isolating post-2020 logging signatures...",
    "Extracting vegetation moisture status (NDMI)...",
    "Benchmarking against local biomass baselines...",
  ],
  "legal_reasoner": [
    "Initializing DeepSeek R1 reasoning core...",
    "Querying EUDR Regulation RAG vector database...",
    "Cross-referencing Article 3.1 compliance...",
    "Validating volume vs productivity coherence...",
    "Building formal legal rationale...",
    "Synthesizing Chain-of-Thought (CoT) audit...",
  ],
  "audit_finalizer": [
    "Generating cryptographically signed report...",
    "Registering SHA-256 hash in audit log...",
    "Optimizing visualization for certificate...",
  ]
};

interface AnalysisLoaderProps {
  activeStage: string | null;
}

export function AnalysisLoader({ activeStage }: AnalysisLoaderProps) {
  const [displayProgress, setDisplayProgress] = useState(0);
  const [currentLabel, setCurrentLabel] = useState("Initializing Analysis Pipeline...");
  const [subIndex, setSubIndex] = useState(0);

  useEffect(() => {
    if (activeStage && STAGE_MAPPING[activeStage]) {
      const { label, progress } = STAGE_MAPPING[activeStage];
      setCurrentLabel(label);
      setDisplayProgress(progress);
      setSubIndex(0); // Reset sub-index on stage change
    }
  }, [activeStage]);

  // Handle sub-message rotation every 10 seconds
  useEffect(() => {
    if (!activeStage) return;
    
    const interval = setInterval(() => {
      setSubIndex((prev) => prev + 1);
    }, 10000);

    return () => clearInterval(interval);
  }, [activeStage]);

  const subMessages = activeStage ? SUB_MAPPING[activeStage] || [] : [];
  const displaySubMessage = subMessages.length > 0 
    ? subMessages[subIndex % subMessages.length] 
    : "Processing geographic intelligence...";

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
      <Text size="sm" c="teal.4" fw={500} ta="center" h={20}>
        <AnimatePresence mode="wait">
          <motion.div
            key={`${activeStage}-${subIndex}`}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            transition={{ duration: 0.4 }}
          >
            {displaySubMessage}
          </motion.div>
        </AnimatePresence>
      </Text>
    </Stack>
  );
}
