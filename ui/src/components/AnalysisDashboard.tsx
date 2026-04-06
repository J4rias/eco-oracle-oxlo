// UI Component
import { Paper, Title, Grid, Badge, RingProgress, Text, Group, Stack, Card, Box, Button } from '@mantine/core';
import { IconCheck, IconX, IconAlertTriangle, IconMapPin, IconExternalLink, IconArrowLeft } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import { MapContainer, TileLayer, Polygon } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface AnalysisDashboardProps {
  report: any; // Ideally typed to ComplianceResponse
  geojson?: any;
  onReset: () => void;
}

export function AnalysisDashboard({ report, geojson, onReset }: AnalysisDashboardProps) {

  // Map verdict to colors
  const getVerdictVisuals = (verdict: string) => {
    switch(verdict) {
      case 'PASS': return { color: 'green', icon: IconCheck, label: 'COMPLIANT' };
      case 'FAIL': return { color: 'red', icon: IconX, label: 'NON-COMPLIANT' };
      default: return { color: 'yellow', icon: IconAlertTriangle, label: 'REQUIRES REVIEW' };
    }
  };

  const visuals = getVerdictVisuals(report?.report?.verdict || 'REQUIRES_HUMAN_REVIEW');
  const VerdictIcon = visuals.icon;

  // Calculate center of polygon roughly (Leaflet expects LatLng)
  let mapCenter: [number, number] = [1.9826, -76.0473];
  let polygonPositions: [number, number][] = [];

  if (geojson?.features?.[0]?.geometry?.coordinates?.[0]) {
    const coords = geojson.features[0].geometry.coordinates[0];
    let minX = 180, minY = 90, maxX = -180, maxY = -90;
    coords.forEach(([x, y]: [number, number]) => {
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      polygonPositions.push([y, x]);
    });
    mapCenter = [(minY + maxY) / 2, (minX + maxX) / 2];
  }

  return (
    <Grid>
      {/* Left side: Map & Metrics */}
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Card shadow="sm" padding="lg" radius="md" withBorder mb="lg">
          <Card.Section>
            {geojson && polygonPositions.length > 0 ? (
              <div style={{ height: 300, width: '100%', position: 'relative', zIndex: 1 }}>
                <MapContainer center={mapCenter} zoom={14} style={{ height: '100%', width: '100%', zIndex: 1, borderRadius: 'md' }}>
                  <TileLayer
                    url="https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                    attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                  />
                  <Polygon 
                    positions={polygonPositions} 
                    pathOptions={{ color: '#12b886', fillColor: '#12b886', fillOpacity: 0.4, weight: 2 }} 
                  />
                </MapContainer>
              </div>
            ) : (
                <div style={{ height: 300, background: 'var(--mantine-color-dark-6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                   <Stack align="center" gap="xs">
                     <IconMapPin size={48} color="var(--mantine-color-dimmed)" />
                     <Text c="dimmed">Polygon Map Layer Data</Text>
                     <Text size="xs" c="dimmed">{(report?.report?.polygon_area_ha || 0).toFixed(2)} Hectares</Text>
                   </Stack>
                </div>
            )}
          </Card.Section>
          <Group justify="space-between" mt="md" mb="xs">
            <Text fw={500}>EUDR Audit Hash</Text>
            <Badge color="pink" variant="light">{(report?.audit_hash || 'PENDING-HASH').substring(0, 16)}...</Badge>
          </Group>
          <Text size="sm" c="dimmed">
            This compliance record has been immutably written to the Supabase log database.
          </Text>
        </Card>

        {/* Risk Score Ring */}
        <Paper shadow="sm" radius="md" p="xl" withBorder>
          <Group justify="center">
             <RingProgress
               size={180}
               thickness={16}
               roundCaps
               sections={[{ value: report?.report?.risk_score || 0, color: visuals.color }]}
               label={
                 <Text c={visuals.color} fw={700} ta="center" size="xl">
                   {report?.report?.risk_score || 0}%
                 </Text>
               }
             />
             <Box>
               <Title order={3}>Risk Score</Title>
               <Text c="dimmed" size="sm">Overall calculated danger index</Text>
             </Box>
          </Group>
        </Paper>
      </Grid.Col>

      {/* Right side: AI Rationale */}
      <Grid.Col span={{ base: 12, md: 7 }}>
        <Paper shadow="sm" radius="md" p="xl" withBorder style={{ height: '100%' }}>
          <Group justify="space-between" mb="xl">
             <Group>
               <Button variant="default" onClick={onReset} leftSection={<IconArrowLeft size={16} />} size="xs" radius="xl">
                 New Audit
               </Button>
               <Title order={2}>AI Assessment</Title>
             </Group>
             <Badge 
               size="xl" 
               color={visuals.color} 
               variant="filled" 
               leftSection={<VerdictIcon size={16} />}
               styles={{ root: { height: '32px' }, label: { overflow: 'visible', lineHeight: 1 } }}
             >
               {visuals.label}
             </Badge>
          </Group>

          {report.report.legal_rationale?.volume_coherence_ok === false && (
            <Paper p="md" radius="md" bg="var(--mantine-color-red-light)" mb="xl">
              <Group>
                <IconAlertTriangle color="var(--mantine-color-red-filled)" />
                <Text c="red" fw={500}>Volume Discrepancy Found</Text>
              </Group>
              <Text size="sm" c="red" mt="xs">{report.report.legal_rationale?.volume_coherence_notes}</Text>
            </Paper>
          )}

          <Title order={4} mb="md" c="dimmed">Legal Reasoning (DeepSeek R1)</Title>
          <Box 
            p="md" 
            style={{ 
              background: 'var(--mantine-color-dark-8)', 
              borderRadius: '8px', 
            }}
          >
            <ReactMarkdown
              components={{
                p: (props) => <Text size="sm" mb="sm" ta="justify" {...props} />,
                strong: (props) => <Text component="span" fw={700} c="var(--mantine-color-teal-4)" {...props} />,
                h1: (props) => <Title order={3} mt="sm" mb="xs" ta="left" {...props} />,
                h2: (props) => <Title order={4} mt="sm" mb="xs" ta="left" {...props} />,
                h3: (props) => <Title order={5} mt="sm" mb="xs" ta="left" {...props} />,
                li: (props) => <Text component="li" size="sm" mb="xs" ta="justify" style={{ marginLeft: '1rem', textAlign: 'justify' }} {...props} />,
                ul: (props) => <ul style={{ paddingLeft: '1rem', marginTop: 0, textAlign: 'justify' }} {...props} />,
                ol: (props) => <ol style={{ paddingLeft: '1rem', marginTop: 0, textAlign: 'justify' }} {...props} />,
              }}
            >
               {report?.report?.legal_rationale?.detailed_rationale?.replace(/```markdown\n?/g, '').replace(/```/g, '') || ''}
            </ReactMarkdown>
          </Box>

          {report.report.legal_rationale?.eudr_articles_cited?.length > 0 && (
            <Group mt="xl">
               <Text fw={500}>Cited EUDR Articles:</Text>
               {report.report.legal_rationale?.eudr_articles_cited.map((art: string) => (
                 <Button 
                   key={art} 
                   component="a" 
                   href="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1115"
                   target="_blank"
                   variant="light" 
                   color="blue"
                   radius="xl"
                   size="xs"
                   rightSection={<IconExternalLink size={14} />}
                 >
                   {art}
                 </Button>
               ))}
            </Group>
          )}
        </Paper>
      </Grid.Col>
    </Grid>
  );
}
