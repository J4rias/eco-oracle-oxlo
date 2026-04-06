import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Container, Paper, Title, Text, Badge, Group, Stack, Loader, Center, Box, Divider } from '@mantine/core';
import { IconCheck, IconX, IconShieldCheck, IconAlertTriangle, IconLeaf } from '@tabler/icons-react';

interface VerificationData {
  verified: boolean;
  audit_hash: string;
  invoice_id: string;
  commodity: string;
  verdict: string;
  issued_at: string;
  issuer: string;
}

const VERDICT_CONFIG = {
  PASS: { label: 'EUDR COMPLIANT', color: 'teal', icon: IconCheck },
  FAIL: { label: 'NON-COMPLIANT', color: 'red', icon: IconX },
  REQUIRES_HUMAN_REVIEW: { label: 'REQUIRES REVIEW', color: 'yellow', icon: IconAlertTriangle },
};

export function VerificationPage() {
  const { hash } = useParams<{ hash: string }>();
  const [data, setData] = useState<VerificationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hash) return;

    fetch(`http://localhost:8000/api/v1/compliance/verify/${hash}`)
      .then(async (res) => {
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.detail?.message || `Record not found (${res.status})`);
        }
        return res.json();
      })
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [hash]);

  const verdictConfig = data?.verdict
    ? (VERDICT_CONFIG[data.verdict as keyof typeof VERDICT_CONFIG] ?? VERDICT_CONFIG.REQUIRES_HUMAN_REVIEW)
    : null;
  const VerdictIcon = verdictConfig?.icon ?? IconShieldCheck;
  const issuedDate = data?.issued_at ? new Date(data.issued_at).toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  }) : 'N/A';

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem 1rem',
    }}>
      <Container size="sm">
        {/* Header */}
        <Center mb="xl">
          <Stack align="center" gap="xs">
            <Group gap="md" align="center">
              <IconLeaf size={48} color="#3FB950" stroke={2.5} />
              <Text 
                size="3.2rem" 
                fw={900} 
                variant="gradient" 
                gradient={{ from: 'teal', to: 'green', deg: 90 }}
                style={{ letterSpacing: '-0.02em', lineHeight: 1 }}
              >
                EcoOracle
              </Text>
            </Group>
            <Text c="dimmed" size="md" fw={500} ta="center">
              Certificate Verification Portal
            </Text>
          </Stack>
        </Center>

        <Paper
          radius="lg"
          p="xl"
          style={{
            border: '1px solid #30363d',
            background: 'rgba(22, 27, 34, 0.95)',
            backdropFilter: 'blur(10px)',
          }}
        >
          {loading && (
            <Center py="xl">
              <Stack align="center" gap="md">
                <Loader color="teal" size="lg" />
                <Text c="dimmed">Querying the EcoOracle registry...</Text>
              </Stack>
            </Center>
          )}

          {error && (
            <Stack align="center" gap="md" py="xl">
              {/* Not verified seal */}
              <Box
                style={{
                  width: 90, height: 90, borderRadius: '50%',
                  background: 'rgba(218, 54, 51, 0.12)',
                  border: '3px solid #DA3633',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                <IconX size={44} color="#DA3633" />
              </Box>
              <Title order={2} c="red">Certificate Not Found</Title>
              <Text c="dimmed" ta="center" maw={380}>
                {error}
              </Text>
              <Paper p="md" radius="md" bg="rgba(218, 54, 51, 0.08)" style={{ border: '1px solid rgba(218,54,51,0.3)', width: '100%' }}>
                <Text size="xs" c="dimmed" ta="center" ff="monospace" style={{ wordBreak: 'break-all' }}>
                  Hash: {hash}
                </Text>
              </Paper>
              <Text size="xs" c="dimmed">This hash was not found in our registry. The certificate may be invalid, tampered, or the record may have expired.</Text>
            </Stack>
          )}

          {data && verdictConfig && (
            <Stack gap="lg">
              {/* Verified seal */}
              <Center>
                <Box
                  style={{
                    width: 100, height: 100, borderRadius: '50%',
                    background: `rgba(63, 185, 80, 0.12)`,
                    border: `3px solid #3FB950`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 0 40px rgba(63,185,80,0.2)',
                  }}
                >
                  <IconShieldCheck size={50} color="#3FB950" />
                </Box>
              </Center>

              <Stack align="center" gap="xs">
                <Badge size="xl" color="teal" variant="light" radius="md" py="md">
                  ✓ VERIFIED CERTIFICATE
                </Badge>
                <Text c="dimmed" size="sm">This certificate exists and is authentic in the EcoOracle registry</Text>
              </Stack>

              <Divider color="#30363d" />

              {/* Verdict */}
              <Group justify="center">
                <Badge
                  size="xl"
                  color={verdictConfig.color}
                  variant="filled"
                  leftSection={<VerdictIcon size={16} />}
                  styles={{ root: { height: '36px' }, label: { overflow: 'visible', lineHeight: 1 } }}
                >
                  {verdictConfig.label}
                </Badge>
              </Group>

              {/* Details table */}
              <Paper p="md" radius="md" bg="rgba(255,255,255,0.03)" style={{ border: '1px solid #30363d' }}>
                <Stack gap="sm">
                  {[
                    { label: 'Invoice ID', value: data.invoice_id },
                    { label: 'Commodity', value: data.commodity },
                    { label: 'Issued', value: issuedDate },
                    { label: 'Issuer', value: data.issuer },
                  ].map(({ label, value }) => (
                    <Group key={label} justify="space-between" wrap="nowrap">
                      <Text size="sm" c="dimmed" fw={500}>{label}</Text>
                      <Text size="sm" ta="right">{value}</Text>
                    </Group>
                  ))}
                </Stack>
              </Paper>

              {/* Hash */}
              <Paper p="sm" radius="md" bg="rgba(255,255,255,0.02)" style={{ border: '1px solid #30363d' }}>
                <Text size="xs" c="dimmed" mb={4} fw={600}>SHA-256 AUDIT HASH</Text>
                <Text size="xs" ff="monospace" c="teal" style={{ wordBreak: 'break-all' }}>
                  {data.audit_hash}
                </Text>
              </Paper>

              <Text size="xs" c="dimmed" ta="center">
                Powered by <Text component="span" c="teal" fw={600}>EcoOracle Intelligence Systems</Text> ·{' '}
                EU Deforestation Regulation 2023/1115
              </Text>
            </Stack>
          )}
        </Paper>
      </Container>
    </div>
  );
}
