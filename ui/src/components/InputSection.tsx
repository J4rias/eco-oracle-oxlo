import { useState } from 'react';
import { Paper, Title, Grid, TextInput, NumberInput, Select, Button, Text, Group, Box } from '@mantine/core';
import { DateInput } from '@mantine/dates';
import { Dropzone } from '@mantine/dropzone';
import type { FileWithPath } from '@mantine/dropzone';
import { IconUpload, IconMap, IconX } from '@tabler/icons-react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';

const schema = z.object({
  crop_type: z.enum(['Coffee', 'Cocoa', 'Soya', 'Palm Oil', 'Beef', 'Wood', 'Rubber', 'Other']),
  harvest_date: z.preprocess((arg) => {
    if (typeof arg === "string" || arg instanceof Date) return new Date(arg);
    return arg;
  }, z.date()),
  invoice_id: z.string().min(1, 'Invoice ID is required').max(128),
  reported_tons: z.number().positive('Must be greater than 0')
});



interface InputSectionProps {
  onSubmit: (file: File, metadata: any) => void;
}

export function InputSection({ onSubmit }: InputSectionProps) {
  const [file, setFile] = useState<FileWithPath | null>(null);

  const { control, handleSubmit, formState: { errors } } = useForm<z.input<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      crop_type: 'Coffee',
      invoice_id: '',
      reported_tons: undefined
    }
  });

  const onFormSubmit = (data: any) => {
    if (!file) return;
    // Format harvest_date to YYYY-MM-DD
    const dateObj = data.harvest_date instanceof Date ? data.harvest_date : new Date(data.harvest_date);
    const ISODate = dateObj.toISOString().split('T')[0];
    const metadata = {
      ...data,
      harvest_date: ISODate
    };
    onSubmit(file, metadata);
  };

  return (
    <Paper shadow="sm" radius="md" p="xl" withBorder>
      <Title order={2} mb="xl">New Compliance Verification</Title>
      
      <Grid>
        {/* Left Column: Dropzone */}
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Dropzone
            onDrop={(files) => setFile(files[0])}
            onReject={() => setFile(null)}
            maxSize={5 * 1024 ** 2}
            accept={{ 'application/json': ['.json', '.geojson'], 'application/geo+json': ['.geojson'] }}
            style={{ height: '100%', minHeight: 250, display: 'flex', justifyContent: 'center', alignItems: 'center' }}
            bg={file ? 'var(--mantine-color-teal-light)' : undefined}
          >
            <Group justify="center" gap="xl" style={{ minHeight: 220, pointerEvents: 'none' }}>
              <Dropzone.Accept>
                <IconUpload size={50} color="var(--mantine-color-blue-6)" stroke={1.5} />
              </Dropzone.Accept>
              <Dropzone.Reject>
                <IconX size={50} color="var(--mantine-color-red-6)" stroke={1.5} />
              </Dropzone.Reject>
              <Dropzone.Idle>
                <IconMap size={50} color="var(--mantine-color-dimmed)" stroke={1.5} />
              </Dropzone.Idle>

              <Box>
                {file ? (
                  <Text size="xl" inline c="white">
                    {file.name} ready for analysis.
                  </Text>
                ) : (
                  <>
                    <Text size="xl" inline>
                      Drag GeoJSON farm profile here or click to select
                    </Text>
                    <Text size="sm" c="dimmed" inline mt={7}>
                      File should not exceed 5mb and map geometry must be Polygon or MultiPolygon.
                    </Text>
                  </>
                )}
              </Box>
            </Group>
          </Dropzone>
          {!file && <Text c="red" size="xs" mt="xs">A GeoJSON boundary file is required.</Text>}
        </Grid.Col>

        {/* Right Column: Metadata Form */}
        <Grid.Col span={{ base: 12, md: 6 }}>
          <form onSubmit={handleSubmit(onFormSubmit)}>
            <Controller
              name="crop_type"
              control={control}
              render={({ field }) => (
                <Select
                  {...field}
                  label="Crop Commodity"
                  placeholder="Select derived commodity"
                  data={['Coffee', 'Cocoa', 'Soya', 'Palm Oil', 'Beef', 'Wood', 'Rubber', 'Other']}
                  error={errors.crop_type?.message}
                  mb="md"
                />
              )}
            />
            
            <Controller
              name="invoice_id"
              control={control}
              render={({ field }) => (
                <TextInput
                  {...field}
                  label="Invoice Identifier"
                  placeholder="e.g. INV-2026-X12"
                  error={errors.invoice_id?.message}
                  mb="md"
                />
              )}
            />
            
            <Controller
              name="harvest_date"
              control={control}
              render={({ field }) => (
                <DateInput
                  {...field}
                  value={field.value as Date | undefined}
                  label="Harvest Date"
                  placeholder="Pick date"
                  error={errors.harvest_date?.message}
                  mb="md"
                />
              )}
            />
            
            <Controller
              name="reported_tons"
              control={control}
              render={({ field }) => (
                <NumberInput
                  {...field}
                  label="Reported Volume (Metric Tons)"
                  placeholder="12.5"
                  min={0.1}
                  step={0.1}
                  error={errors.reported_tons?.message}
                  mb="xl"
                />
              )}
            />
            
            <Button 
              type="submit" 
              size="lg" 
              fullWidth 
              variant="gradient" 
              gradient={{ from: 'teal', to: 'blue', deg: 60 }}
              disabled={!file}
            >
              Analyze Compliance
            </Button>
          </form>
        </Grid.Col>
      </Grid>
    </Paper>
  );
}
