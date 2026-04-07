// UI Component
import { useState } from 'react';
import { Paper, Title, Grid, Badge, Text, Group, Stack, Card, Box, Button, Tooltip, Modal, ActionIcon } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconCheck, IconX, IconAlertTriangle, IconMapPin, IconExternalLink, IconArrowLeft, IconDownload, IconShield, IconAlertCircle, IconAlertOctagon, IconMaximize } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import { MapContainer, TileLayer, Polygon, LayersControl, ImageOverlay } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface AnalysisDashboardProps {
  report: any; // Ideally typed to ComplianceResponse
  geojson?: any;
  onReset: () => void;
}

export function AnalysisDashboard({ report, geojson, onReset }: AnalysisDashboardProps) {
  const [opened, { open, close }] = useDisclosure(false);

  // Risk score categorization
  const getRiskCategory = (score: number) => {
    if (score <= 30) return {
      label: 'LOW RISK', color: 'teal', icon: IconShield,
      description: 'No significant deforestation indicators detected. Farm shows strong EUDR compliance signals.',
      ringColor: 'teal',
    };
    if (score <= 70) return {
      label: 'MODERATE RISK', color: 'yellow', icon: IconAlertCircle,
      description: 'Some anomalies detected requiring attention. Manual review is recommended before export clearance.',
      ringColor: 'yellow',
    };
    if (score === 100 && report.report.verdict === 'REJECTED_URBAN_AREA') return {
      label: 'URBAN REJECTION', color: 'dark', icon: IconMapPin,
      description: 'The area analyzed is identified as a high-density urban or industrial center. Geo-spatial auditing for EUDR is only valid for forest or agricultural land.',
      ringColor: 'dark',
    };
    return {
      label: 'CRITICAL RISK', color: 'red', icon: IconAlertOctagon,
      description: 'Significant deforestation or compliance violations detected. EU market access may be blocked.',
      ringColor: 'red',
    };
  };

  // Map verdict to colors
  const getVerdictVisuals = (verdict: string) => {
    switch(verdict) {
      case 'PASS': return { color: 'green', icon: IconCheck, label: 'COMPLIANT' };
      case 'FAIL': return { color: 'red', icon: IconX, label: 'NON-COMPLIANT' };
      case 'REJECTED_URBAN_AREA': return { color: 'dark', icon: IconMapPin, label: 'INVALID: URBAN AREA' };
      default: return { color: 'yellow', icon: IconAlertTriangle, label: 'REQUIRES REVIEW' };
    }
  };

  const visuals = getVerdictVisuals(report?.report?.verdict || 'REQUIRES_HUMAN_REVIEW');
  const riskScore = report?.report?.risk_score || 0;
  const riskCategory = getRiskCategory(riskScore);
  const RiskIcon = riskCategory.icon;
  const VerdictIcon = visuals.icon;
  const [isDownloading, setIsDownloading] = useState(false);

  const handleDownloadCertificate = async () => {
    const auditHash = report?.audit_hash;
    if (!auditHash) return;
    setIsDownloading(true);
    try {
      const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${baseUrl}/api/v1/compliance/certificate/${auditHash}`);
      if (!res.ok) throw new Error('Certificate not available. Please run analysis first.');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `EcoOracle_Certificate_${report.report?.invoice_id || 'report'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setIsDownloading(false);
    }
  };

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
  // Prepare imagery bounds for ImageOverlay
  const bbox = report?.evidence?.bounding_box; // [W, S, E, N]
  const imageBounds: [[number, number], [number, number]] | null = bbox 
    ? [[bbox[1], bbox[0]], [bbox[3], bbox[2]]] 
    : null;

  return (
    <Grid>
      {/* Left side: Map & Metrics */}
      <Grid.Col span={{ base: 12, md: 5 }}>
        <Card shadow="sm" padding="lg" radius="md" withBorder mb="lg">
          <Card.Section>
            {geojson && polygonPositions.length > 0 ? (
              <div style={{ height: 300, width: '100%', position: 'relative', zIndex: 1 }}>
                 <ActionIcon 
                    variant="filled" 
                    color="dark" 
                    size="lg" 
                    onClick={open} 
                    style={{ position: 'absolute', bottom: 12, left: 12, zIndex: 1000, boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}
                  >
                    <IconMaximize size={18} />
                  </ActionIcon>
                 <MapContainer center={mapCenter} zoom={14} style={{ height: '100%', width: '100%', zIndex: 1, borderRadius: 'md' }}>
                   <TileLayer
                     url="https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
                     attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                   />
                   
                   <LayersControl position="topright">
                     {imageBounds && report.evidence.sentinel_image_url && (
                       <LayersControl.Overlay name="True Color (RGB)" checked>
                         <ImageOverlay 
                           url={report.evidence.sentinel_image_url} 
                           bounds={imageBounds} 
                           opacity={0.9} 
                         />
                       </LayersControl.Overlay>
                     )}

                     {imageBounds && report.evidence.ndvi_image_url && (
                       <LayersControl.Overlay name="NDVI (Biomass)">
                         <ImageOverlay 
                           url={report.evidence.ndvi_image_url} 
                           bounds={imageBounds} 
                           opacity={0.9} 
                         />
                       </LayersControl.Overlay>
                     )}

                     {imageBounds && report.evidence.ndmi_image_url && (
                       <LayersControl.Overlay name="Moisture Index (NDMI)">
                         <ImageOverlay 
                           url={report.evidence.ndmi_image_url} 
                           bounds={imageBounds} 
                           opacity={0.9} 
                         />
                       </LayersControl.Overlay>
                     )}

                     {imageBounds && report.evidence.detection_overlay_url && (
                       <LayersControl.Overlay name="Vision Input (SWIR)">
                         <ImageOverlay 
                           url={report.evidence.detection_overlay_url} 
                           bounds={imageBounds} 
                           opacity={0.9} 
                         />
                       </LayersControl.Overlay>
                     )}
                   </LayersControl>

                   <Polygon 
                     positions={polygonPositions} 
                     pathOptions={{ color: '#12b886', fillColor: 'transparent', weight: 3 }} 
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
          <Group justify="space-between" mt="md" mb="xs" align="center">
            <Text fw={500}>EUDR Audit Hash</Text>
            <Badge color="pink" variant="light" size="sm">{(report?.audit_hash || 'PENDING-HASH').substring(0, 16)}...</Badge>
          </Group>
          <Text size="sm" c="dimmed">
            This compliance record has been immutably written to the Supabase log database.
          </Text>
        </Card>

        {/* Risk Score */}
        <Paper shadow="sm" radius="md" p="xl" withBorder>
          <Stack gap="md">
            <Group justify="space-between" align="center">
              <Box>
                <Title order={4}>Risk Score</Title>
                <Text c="dimmed" size="xs" mt={2}>EUDR Compliance Risk Index</Text>
              </Box>
              <Badge
                size="lg"
                color={riskCategory.color}
                variant="light"
                leftSection={<RiskIcon size={14} />}
                h={30}
                styles={{ 
                  root: { border: `1px solid var(--mantine-color-${riskCategory.color}-outline)` },
                  label: { paddingTop: '1px' }
                }}
              >
                {riskCategory.label}
              </Badge>
            </Group>

            <Grid align="center" mt="sm">
              <Grid.Col span={6}>
                {/* Custom SVG ring — avoids Mantine label centering quirks */}
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                  <div style={{ position: 'relative', width: 140, height: 140 }}>
                    <svg width="140" height="140" viewBox="0 0 140 140">
                      {/* Background track */}
                      <circle
                        cx="70" cy="70" r="56"
                        fill="none"
                        stroke="var(--mantine-color-dark-4)"
                        strokeWidth="12"
                      />
                      {/* Progress arc */}
                      <circle
                        cx="70" cy="70" r="56"
                        fill="none"
                        stroke={riskCategory.ringColor === 'teal' ? '#12b886' : riskCategory.ringColor === 'yellow' ? '#fab005' : '#fa5252'}
                        strokeWidth="12"
                        strokeLinecap="round"
                        strokeDasharray={`${(riskScore / 100) * 2 * Math.PI * 56} ${2 * Math.PI * 56}`}
                        transform="rotate(-90 70 70)"
                      />
                    </svg>
                    {/* Centered label overlay */}
                    <div style={{
                      position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                    }}>
                      <span style={{ fontSize: '2.2rem', fontWeight: 900, lineHeight: 1, color: riskCategory.ringColor === 'teal' ? '#12b886' : riskCategory.ringColor === 'yellow' ? '#fab005' : '#fa5252' }}>
                        {riskScore}
                      </span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--mantine-color-dimmed)', marginTop: 2 }}>/ 100</span>
                    </div>
                  </div>
                </div>
              </Grid.Col>

              <Grid.Col span={6}>
                <Box pl="xs">
                  <Text size="xs" c="dimmed" lh={1.4}>
                    {riskCategory.description}
                  </Text>
                </Box>
              </Grid.Col>
            </Grid>

            {/* Risk scale legend */}
            <Group gap="xs" justify="center">
              {[{ label: '0–30', text: 'Low', color: 'teal' }, { label: '31–70', text: 'Moderate', color: 'yellow' }, { label: '71–100', text: 'Critical', color: 'red' }].map(t => (
                <Tooltip key={t.label} label={t.label} withArrow>
                  <Badge size="xs" color={t.color} variant={riskCategory.color === t.color ? 'filled' : 'outline'}>
                    {t.text}
                  </Badge>
                </Tooltip>
              ))}
            </Group>
          </Stack>
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
             <Group gap="xs">
               <Button
                 variant="light"
                 color="teal"
                 size="xs"
                 radius="xl"
                 leftSection={<IconDownload size={14} />}
                 onClick={handleDownloadCertificate}
                 loading={isDownloading}
               >
                 Certificate
               </Button>
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

      <Modal 
        opened={opened} 
        onClose={close} 
        size="90%" 
        title={`Satellite Evidence Analyzer — ${report.report.invoice_id}`}
        overlayProps={{ backgroundOpacity: 0.55, blur: 3 }}
        centered
        radius="md"
      >
        <div style={{ height: '75vh', width: '100%' }}>
          <MapContainer center={mapCenter} zoom={15} style={{ height: '100%', width: '100%' }}>
            <TileLayer
              url="https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            />
            <LayersControl position="topright">
              {imageBounds && report.evidence.sentinel_image_url && (
                <LayersControl.Overlay name="True Color (RGB)" checked>
                  <ImageOverlay url={report.evidence.sentinel_image_url} bounds={imageBounds} opacity={1} />
                </LayersControl.Overlay>
              )}
              {imageBounds && report.evidence.ndvi_image_url && (
                <LayersControl.Overlay name="NDVI (Biomass)">
                  <ImageOverlay url={report.evidence.ndvi_image_url} bounds={imageBounds} opacity={1} />
                </LayersControl.Overlay>
              )}
              {imageBounds && report.evidence.ndmi_image_url && (
                <LayersControl.Overlay name="Moisture Index (NDMI)">
                  <ImageOverlay url={report.evidence.ndmi_image_url} bounds={imageBounds} opacity={1} />
                </LayersControl.Overlay>
              )}
              {imageBounds && report.evidence.detection_overlay_url && (
                <LayersControl.Overlay name="Vision Input (SWIR)">
                  <ImageOverlay url={report.evidence.detection_overlay_url} bounds={imageBounds} opacity={1} />
                </LayersControl.Overlay>
              )}
            </LayersControl>
            <Polygon positions={polygonPositions} pathOptions={{ color: '#12b886', fillColor: 'transparent', weight: 3 }} />
          </MapContainer>
        </div>
        <Group justify="center" mt="md">
          <Text size="sm" c="dimmed">
            Spectral images are captured by Sentinel-2 L2A satellite clusters · Resolution 10m/px
          </Text>
        </Group>
      </Modal>
    </Grid>
  );
}
