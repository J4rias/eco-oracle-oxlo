import { useState } from 'react';
import { Container, Title, Text, Paper, Transition, Flex, Loader, Center } from '@mantine/core';
import { Toaster, toast } from 'sonner';
import { InputSection } from './components/InputSection';
import { AnalysisDashboard } from './components/AnalysisDashboard';
import { useMutation } from '@tanstack/react-query';

export function App() {
  const [report, setReport] = useState<any>(null);
  const [geojsonData, setGeojsonData] = useState<any>(null);
  
  // API Call Mutation
  const analyzeMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const response = await fetch('http://localhost:8000/api/v1/compliance/analyze', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        let errMsg = `Server returned ${response.status}`;
        try {
          const errData = await response.json();
          if (errData.detail) errMsg = typeof errData.detail === 'string' ? errData.detail : JSON.stringify(errData.detail);
          else if (errData.error) errMsg = errData.error;
        } catch(e) {}
        throw new Error(errMsg);
      }
      return response.json();
    },
    onSuccess: (data) => {
      setReport(data);
      toast.success('Compliance analysis completed successfully.');
    },
    onError: (error) => {
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
            <Text component="h1" size="3rem" fw={900} variant="gradient" gradient={{ from: 'teal', to: 'green', deg: 90 }}>
              EcoOracle
            </Text>
            <Text color="dimmed" size="lg">Geographic Intelligence & EUDR Compliance Agent</Text>
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
                <Center style={{ height: '300px', flexDirection: 'column', gap: '1rem' }}>
                  <Loader size="xl" type="bars" color="teal" />
                  <Title order={3}>Running EcoOracle AI Pipeline...</Title>
                  <Text color="dimmed">Fetching Sentinel-2 Imagery and applying DeepSeek legal reasoning.</Text>
                </Center>
              </Paper>
            )}

            {report && (
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
