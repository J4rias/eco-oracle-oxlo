import { useState } from 'react';
import { Container, Text, Paper, Transition, Flex, Group, Center, Stack } from '@mantine/core';
import { IconLeaf } from '@tabler/icons-react';
import { Toaster, toast } from 'sonner';
import { InputSection } from './components/InputSection';
import { AnalysisDashboard } from './components/AnalysisDashboard';
import { AnalysisLoader } from './components/AnalysisLoader';
import { useMutation } from '@tanstack/react-query';

import { API_BASE_URL } from './config';

export function App() {
  const [report, setReport] = useState<any>(null);
  const [geojsonData, setGeojsonData] = useState<any>(null);
  const [activeStage, setActiveStage] = useState<string | null>(null);
  
  // API Call Mutation
  const analyzeMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await fetch(`${API_BASE_URL}/api/v1/compliance/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error(`Server returned ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let finalData = null;

      while (reader) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event = JSON.parse(line.replace('data: ', ''));
              if (event.type === 'stage') {
                setActiveStage(event.node);
              } else if (event.type === 'final') {
                finalData = event.data;
              } else if (event.type === 'error') {
                throw new Error(event.detail);
              }
            } catch (e) {
              console.error("Error parsing stream chunk", e);
            }
          }
        }
      }
      return finalData;
    },
    onSuccess: (data) => {
      setReport(data);
      setActiveStage(null);
      toast.success('Compliance analysis completed successfully.');
    },
    onError: (error) => {
      setActiveStage(null);
      toast.error(`Analysis failed: ${error.message}`);
    }
  });

  const handleAnalyze = async (file: File, metadata: any) => {
    try {
      const text = await file.text();
      setGeojsonData(JSON.parse(text));
    } catch(e) {
      console.warn("Could not parse GeoJSON for preview");
    }

    const formData = new FormData();
    formData.append('geojson_file', file);
    formData.append('metadata', JSON.stringify(metadata));
    analyzeMutation.mutate(formData);
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--mantine-color-body)', padding: '2rem 1rem' }}>
      <Toaster richColors position="top-right" />
      
      <Container size="xl">
        <Flex direction="column" gap="xl">
          <header>
            <Center mb="xs">
              <Stack align="center" gap="xs">
                <Group gap="md" align="center">
                  <IconLeaf size={58} color="#3FB950" stroke={2.5} />
                  <Text 
                    component="h1" 
                    size="4.5rem" 
                    fw={900} 
                    variant="gradient" 
                    gradient={{ from: 'teal', to: 'green', deg: 90 }}
                    style={{ letterSpacing: '-0.02em', lineHeight: 1 }}
                  >
                    EcoOracle
                  </Text>
                </Group>
                <Text color="dimmed" size="lg" ta="center" fw={500}>
                  Geographic Intelligence & EUDR Compliance Agent
                </Text>
              </Stack>
            </Center>
          </header>

          <main>
            {!report && !analyzeMutation.isPending && (
              <Transition mounted={!report && !analyzeMutation.isPending} transition="fade" duration={400}>
                {(styles) => (
                  <div style={styles}>
                    <InputSection onSubmit={handleAnalyze} />
                  </div>
                )}
              </Transition>
            )}

            {analyzeMutation.isPending && (
              <Paper p="xl" radius="md" style={{ background: 'rgba(255, 255, 255, 0.05)', backdropFilter: 'blur(10px)' }}>
                <AnalysisLoader activeStage={activeStage} />
              </Paper>
            )}

            {report && report?.report?.legal_rationale && (
              <Transition mounted={!!report} transition="slide-up" duration={500}>
                {(styles) => (
                  <div style={styles}>
                    <AnalysisDashboard 
                      report={report} 
                      geojson={geojsonData} 
                      onReset={() => {
                        setReport(null);
                        setGeojsonData(null);
                        analyzeMutation.reset();
                      }}
                    />
                  </div>
                )}
              </Transition>
            )}
          </main>
        </Flex>
      </Container>
    </div>
  );
}

export default App;
