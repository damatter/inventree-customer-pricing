import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Group,
  LoadingOverlay,
  Modal,
  NumberInput,
  Paper,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Textarea,
  TextInput,
  Title
} from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useCallback, useEffect, useMemo, useState } from 'react';

type PricingPluginContext = {
  id?: string | number | null;
  context?: { part_id?: number };
  locale: string;
  theme: { primaryColor: string };
  api: {
    get: <T = WorkspaceData>(url: string) => Promise<{ data: T }>;
    request: (config: {
      method: 'post' | 'patch' | 'delete';
      url: string;
      data?: Record<string, unknown>;
    }) => Promise<unknown>;
  };
};

type NativeBreak = {
  pk: number;
  quantity: string;
  price: string | null;
  currency: string;
};

type CustomerBreak = NativeBreak & {
  price_list: number;
  material_cost: string | null;
  profit_amount: string | null;
  profit_margin_percent: string | null;
};

type CustomerPriceList = {
  pk: number;
  part: number;
  customer: number;
  customer_name: string;
  currency: string;
  active: boolean;
  notes: string;
  material_cost: string | null;
  base_selling_price: string | null;
  profit_amount: string | null;
  profit_margin_percent: string | null;
  breaks: CustomerBreak[];
  created: string;
  updated: string;
};

type MaterialCostEntry = {
  pk: number;
  part: number;
  name: string;
  quantity: string;
  unit_cost: string;
  currency: string;
  total_cost: string;
  active: boolean;
  notes: string;
};

type WorkspaceData = {
  part: {
    pk: number;
    name: string;
    ipn: string;
    salable: boolean;
    purchaseable: boolean;
  };
  permissions: {
    view_sales: boolean;
    change_sales: boolean;
    view_purchase: boolean;
    change_purchase: boolean;
  };
  policy: {
    resolved_currency: string;
  };
  customer_lists: CustomerPriceList[];
  customers: { pk: number; name: string; currency: string }[];
  material_costs: MaterialCostEntry[];
  material_cost_summary: { currency: string; total: string }[];
  material_cost_errors: Record<string, string>;
  currencies: string[];
};

type ListEditorState = {
  record?: CustomerPriceList;
  customer: string | null;
  currency: string | null;
  active: boolean;
  notes: string;
};

type MaterialEditorState = {
  record?: MaterialCostEntry;
  name: string;
  quantity: string | number;
  unitCost: string | number;
  currency: string | null;
  active: boolean;
  notes: string;
};

type BreakEditorState = {
  ownerId: number;
  record?: NativeBreak | CustomerBreak;
  quantity: string | number;
  price: string | number;
  currency: string | null;
};

type ConfirmationState = {
  title: string;
  message: string;
  action: () => Promise<void>;
};

function apiErrorMessage(error: unknown): string {
  const apiError = error as { response?: { data?: unknown }; message?: string };
  const payload = apiError.response?.data;

  if (!payload) {
    return apiError.message || 'The pricing request failed.';
  }

  if (typeof payload === 'string') {
    return payload;
  }

  return Object.entries(payload as Record<string, unknown>)
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
    .join(' | ');
}

function formatMoney(value: string | null, currency: string, locale: string): string {
  if (value === null || value === '') {
    return '\u2014';
  }

  try {
    return new Intl.NumberFormat(locale || 'en', {
      style: 'currency',
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(Number(value));
  } catch {
    return `${currency} ${value}`;
  }
}

function formatQuantity(value: string): string {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Paper withBorder radius="md" p="md">
      <Text size="xs" fw={700} tt="uppercase" c="dimmed">
        {label}
      </Text>
      <Text fz={28} fw={750} lh={1.15} mt={4}>
        {value}
      </Text>
      <Text size="sm" c="dimmed" mt={4}>
        {detail}
      </Text>
    </Paper>
  );
}

function EmptyState({ title, message }: { title: string; message: string }) {
  return (
    <Paper withBorder radius="md" p="xl">
      <Stack gap={4} align="center">
        <Text fw={700}>{title}</Text>
        <Text size="sm" c="dimmed" ta="center">
          {message}
        </Text>
      </Stack>
    </Paper>
  );
}

function BreakTable({
  records,
  currency,
  locale,
  editable,
  showMargin = false,
  onEdit,
  onDelete
}: {
  records: (NativeBreak | CustomerBreak)[];
  currency: string;
  locale: string;
  editable: boolean;
  showMargin?: boolean;
  onEdit: (record: NativeBreak | CustomerBreak) => void;
  onDelete: (record: NativeBreak | CustomerBreak) => void;
}) {
  if (records.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        No quantity breaks have been added.
      </Text>
    );
  }

  return (
    <ScrollArea>
      <Table striped highlightOnHover verticalSpacing="sm" miw={520}>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Minimum quantity</Table.Th>
            <Table.Th>Unit price</Table.Th>
            {showMargin && <Table.Th>Material cost</Table.Th>}
            {showMargin && <Table.Th>Gross profit</Table.Th>}
            {showMargin && <Table.Th>Margin</Table.Th>}
            {editable && <Table.Th ta="right">Actions</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {records.map((record) => {
            const customerRecord = record as CustomerBreak;
            return (
              <Table.Tr key={record.pk}>
                <Table.Td fw={600}>{formatQuantity(record.quantity)}</Table.Td>
                <Table.Td>
                  {formatMoney(record.price, record.currency || currency, locale)}
                </Table.Td>
                {showMargin && (
                  <Table.Td>
                    {formatMoney(customerRecord.material_cost, record.currency || currency, locale)}
                  </Table.Td>
                )}
                {showMargin && (
                  <Table.Td>
                    {formatMoney(customerRecord.profit_amount, record.currency || currency, locale)}
                  </Table.Td>
                )}
                {showMargin && (
                  <Table.Td>
                    {customerRecord.profit_margin_percent === null
                      ? '\u2014'
                      : `${Number(customerRecord.profit_margin_percent).toFixed(2)}%`}
                  </Table.Td>
                )}
                {editable && (
                  <Table.Td>
                    <Group gap="xs" justify="flex-end" wrap="nowrap">
                      <Button size="compact-xs" variant="subtle" onClick={() => onEdit(record)}>
                        Edit
                      </Button>
                      <Button
                        size="compact-xs"
                        variant="subtle"
                        color="red"
                        onClick={() => onDelete(record)}
                      >
                        Delete
                      </Button>
                    </Group>
                  </Table.Td>
                )}
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}

function CustomerPricingPanel({ context }: { context: PricingPluginContext }) {
  const partId = Number(context.id ?? context.context?.part_id);
  const apiBase = `/plugin/customer-pricing/part/${partId}`;

  const [data, setData] = useState<WorkspaceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listEditor, setListEditor] = useState<ListEditorState | null>(null);
  const [materialEditor, setMaterialEditor] = useState<MaterialEditorState | null>(null);
  const [breakEditor, setBreakEditor] = useState<BreakEditorState | null>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationState | null>(null);

  const loadWorkspace = useCallback(async () => {
    if (!Number.isFinite(partId)) {
      setError('No valid part was provided to the pricing plugin.');
      setLoading(false);
      return;
    }

    try {
      setError(null);
      const response = await context.api.get(`${apiBase}/`);
      setData(response.data);
    } catch (requestError) {
      setError(apiErrorMessage(requestError));
    } finally {
      setLoading(false);
    }
  }, [apiBase, context.api, partId]);

  useEffect(() => {
    loadWorkspace();
  }, [loadWorkspace]);

  const request = useCallback(
    async (
      method: 'post' | 'patch' | 'delete',
      url: string,
      payload?: Record<string, unknown>,
      successMessage?: string
    ) => {
      setBusy(true);
      try {
        await context.api.request({ method, url, data: payload });
        if (successMessage) {
          notifications.show({
            title: 'Pricing updated',
            message: successMessage,
            color: 'teal'
          });
        }
        await loadWorkspace();
      } catch (requestError) {
        notifications.show({
          title: 'Could not update pricing',
          message: apiErrorMessage(requestError),
          color: 'red'
        });
        throw requestError;
      } finally {
        setBusy(false);
      }
    },
    [context.api, loadWorkspace]
  );

  const customerTierCount = useMemo(
    () => data?.customer_lists.reduce((sum, priceList) => sum + priceList.breaks.length, 0) ?? 0,
    [data]
  );

  const resolvedMaterialTotal = useMemo(() => {
    if (!data) {
      return null;
    }
    return (
      data.material_cost_summary.find(
        (summary) => summary.currency === data.policy.resolved_currency
      )?.total ?? null
    );
  }, [data]);

  const headlineSchedule = useMemo(
    () =>
      data?.customer_lists.find(
        (priceList) => priceList.active && priceList.base_selling_price !== null
      ) ?? null,
    [data]
  );

  const availableCustomers = useMemo(() => {
    if (!data) {
      return [];
    }

    const selectedCustomer = Number(listEditor?.customer);
    const currentCustomer =
      listEditor?.record?.customer ??
      (Number.isFinite(selectedCustomer) ? selectedCustomer : undefined);
    const used = new Set(
      data.customer_lists
        .filter((priceList) => priceList.customer !== currentCustomer)
        .map((priceList) => priceList.customer)
    );

    return data.customers
      .filter((customer) => !used.has(customer.pk))
      .map((customer) => ({ value: String(customer.pk), label: customer.name }));
  }, [data, listEditor]);

  const openNewList = () => {
    setListEditor({
      customer: null,
      currency: data?.policy.resolved_currency ?? 'USD',
      active: true,
      notes: ''
    });
  };

  const openEditList = (record: CustomerPriceList) => {
    setListEditor({
      record,
      customer: String(record.customer),
      currency: record.currency,
      active: record.active,
      notes: record.notes
    });
  };

  const saveList = async () => {
    if (!listEditor?.customer || !listEditor.currency) {
      return;
    }

    const editor = listEditor;
    const payload = {
      customer: Number(editor.customer),
      currency: editor.currency,
      active: editor.active,
      notes: editor.notes
    };
    const url = editor.record
      ? `${apiBase}/customer-lists/${editor.record.pk}/`
      : `${apiBase}/customer-lists/`;

    setListEditor(null);
    try {
      await request(
        editor.record ? 'patch' : 'post',
        url,
        payload,
        editor.record ? 'Customer price list saved.' : 'Customer price list created.'
      );
    } catch {
      setListEditor(editor);
    }
  };

  const openNewMaterial = () => {
    setMaterialEditor({
      name: '',
      quantity: 1,
      unitCost: '',
      currency: data?.policy.resolved_currency ?? 'USD',
      active: true,
      notes: ''
    });
  };

  const openEditMaterial = (record: MaterialCostEntry) => {
    setMaterialEditor({
      record,
      name: record.name,
      quantity: record.quantity,
      unitCost: record.unit_cost,
      currency: record.currency,
      active: record.active,
      notes: record.notes
    });
  };

  const saveMaterial = async () => {
    if (
      !materialEditor?.name.trim() ||
      materialEditor.quantity === '' ||
      materialEditor.unitCost === '' ||
      !materialEditor.currency
    ) {
      return;
    }

    const payload = {
      name: materialEditor.name.trim(),
      quantity: materialEditor.quantity,
      unit_cost: materialEditor.unitCost,
      currency: materialEditor.currency,
      active: materialEditor.active,
      notes: materialEditor.notes
    };
    const url = materialEditor.record
      ? `${apiBase}/material-costs/${materialEditor.record.pk}/`
      : `${apiBase}/material-costs/`;

    await request(
      materialEditor.record ? 'patch' : 'post',
      url,
      payload,
      materialEditor.record ? 'Material cost saved.' : 'Material cost added.'
    );
    setMaterialEditor(null);
  };

  const askDeleteMaterial = (record: MaterialCostEntry) => {
    setConfirmation({
      title: 'Delete material cost?',
      message: `This removes ${record.name} from the material cost and margin calculations.`,
      action: async () => {
        await request(
          'delete',
          `${apiBase}/material-costs/${record.pk}/`,
          undefined,
          'Material cost deleted.'
        );
      }
    });
  };

  const openBreakEditor = (
    ownerId: number,
    currency: string,
    record?: NativeBreak | CustomerBreak
  ) => {
    setBreakEditor({
      ownerId,
      record,
      quantity: record?.quantity ?? 1,
      price: record?.price ?? '',
      currency: record?.currency || currency
    });
  };

  const saveBreak = async () => {
    if (!breakEditor || breakEditor.price === '' || !breakEditor.currency) {
      return;
    }

    const payload = {
      quantity: breakEditor.quantity,
      price: breakEditor.price
    };
    const url = breakEditor.record
      ? `${apiBase}/customer-breaks/${breakEditor.record.pk}/`
      : `${apiBase}/customer-lists/${breakEditor.ownerId}/breaks/`;

    await request(
      breakEditor.record ? 'patch' : 'post',
      url,
      payload,
      breakEditor.record ? 'Price break saved.' : 'Price break added.'
    );
    setBreakEditor(null);
  };

  const askDeleteList = (record: CustomerPriceList) => {
    setConfirmation({
      title: 'Delete customer price list?',
      message: `This removes every ${record.customer_name} price break for this part. InvenTree pricing will be synchronized immediately.`,
      action: async () => {
        await request(
          'delete',
          `${apiBase}/customer-lists/${record.pk}/`,
          undefined,
          'Customer price list deleted.'
        );
      }
    });
  };

  const askDeleteBreak = (record: NativeBreak | CustomerBreak) => {
    setConfirmation({
      title: 'Delete price break?',
      message: `The quantity ${formatQuantity(record.quantity)} price break will be removed.`,
      action: async () => {
        await request(
          'delete',
          `${apiBase}/customer-breaks/${record.pk}/`,
          undefined,
          'Price break deleted.'
        );
      }
    });
  };

  const defaultTab = data?.permissions.view_purchase ? 'materials' : 'customers';

  if (loading) {
    return (
      <Paper pos="relative" mih={240}>
        <LoadingOverlay visible />
      </Paper>
    );
  }

  if (error || !data) {
    return (
      <Alert color="red" title="Part Pricing could not load">
        {error || 'No pricing data was returned.'}
      </Alert>
    );
  }

  return (
    <Stack gap="lg" pos="relative">
      <LoadingOverlay visible={busy} overlayProps={{ blur: 1 }} />

      <Paper
        radius="lg"
        p="lg"
        style={{
          background: `linear-gradient(135deg, var(--mantine-color-${context.theme.primaryColor}-8), var(--mantine-color-${context.theme.primaryColor}-6))`,
          color: 'white'
        }}
      >
        <Group justify="space-between" align="flex-start" wrap="wrap">
          <Stack gap={3}>
            <Text size="xs" fw={700} tt="uppercase" opacity={0.8}>
              Pricing workspace
            </Text>
            <Title order={3}>{data.part.ipn || data.part.name}</Title>
            <Text size="sm" opacity={0.9}>
              Material costs, customer schedules, and margins in one place
            </Text>
          </Stack>
          <Badge color="teal" variant="filled" size="lg">
            Highest customer pricing syncs automatically
          </Badge>
        </Group>

        <SimpleGrid cols={{ base: 1, sm: 3 }} mt="lg">
          {[
            {
              label: 'Material cost',
              value: formatMoney(
                headlineSchedule?.material_cost ?? resolvedMaterialTotal,
                headlineSchedule?.currency ?? data.policy.resolved_currency,
                context.locale
              ),
              detail: `${data.material_costs.filter((entry) => entry.active).length} active entries`
            },
            {
              label: 'Gross profit',
              value: formatMoney(
                headlineSchedule?.profit_amount ?? null,
                headlineSchedule?.currency ?? data.policy.resolved_currency,
                context.locale
              ),
              detail: headlineSchedule?.customer_name ?? 'Add a customer selling price'
            },
            {
              label: 'Profit margin',
              value:
                headlineSchedule?.profit_margin_percent === null || !headlineSchedule
                  ? '\u2014'
                  : `${Number(headlineSchedule.profit_margin_percent).toFixed(2)}%`,
              detail: headlineSchedule
                ? `${headlineSchedule.customer_name} base tier`
                : 'Calculated from selling price and materials'
            }
          ].map((metric) => (
            <Paper
              key={metric.label}
              radius="md"
              p="sm"
              style={{ background: 'rgba(255, 255, 255, 0.14)', color: 'white' }}
            >
              <Text size="xs" fw={700} tt="uppercase" opacity={0.8}>
                {metric.label}
              </Text>
              <Text size="xl" fw={750} truncate>
                {metric.value}
              </Text>
              <Text size="xs" opacity={0.85} truncate>
                {metric.detail}
              </Text>
            </Paper>
          ))}
        </SimpleGrid>
      </Paper>

      {(data.permissions.view_sales || data.permissions.view_purchase) && (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          {data.permissions.view_purchase && (
            <MetricCard
              label="Material cost"
              value={formatMoney(
                resolvedMaterialTotal,
                data.policy.resolved_currency,
                context.locale
              )}
              detail={`${data.material_costs.filter((entry) => entry.active).length} active material entries`}
            />
          )}
          {data.permissions.view_sales && (
            <MetricCard
              label="Priced customers"
              value={String(data.customer_lists.length)}
              detail={`${data.customer_lists.filter((priceList) => priceList.active).length} active schedules`}
            />
          )}
          {data.permissions.view_sales && (
            <MetricCard
              label="Customer tiers"
              value={String(customerTierCount)}
              detail="Across all customer schedules"
            />
          )}
        </SimpleGrid>
      )}

      <Tabs defaultValue={defaultTab} keepMounted={false}>
        <Tabs.List>
          {data.permissions.view_purchase && <Tabs.Tab value="materials">Material costs</Tabs.Tab>}
          {data.permissions.view_sales && <Tabs.Tab value="customers">Customer pricing</Tabs.Tab>}
        </Tabs.List>

        {data.permissions.view_purchase && (
          <Tabs.Panel value="materials" pt="lg">
            <Stack gap="md">
              <Group justify="space-between" align="flex-start">
                <Stack gap={2}>
                  <Text fw={700}>Materials used per part</Text>
                  <Text size="sm" c="dimmed">
                    Add one row for each material input. Quantity × unit cost is included in every
                    customer margin automatically.
                  </Text>
                </Stack>
                {data.permissions.change_purchase && (
                  <Button onClick={openNewMaterial}>Add material</Button>
                )}
              </Group>

              {Object.values(data.material_cost_errors).map((message) => (
                <Alert key={message} color="orange" title="Currency conversion unavailable">
                  {message}
                </Alert>
              ))}

              {data.material_costs.length === 0 ? (
                <EmptyState
                  title="No material costs yet"
                  message="Add a material name, quantity and unit cost to start calculating margins."
                />
              ) : (
                data.material_costs.map((material) => (
                  <Card key={material.pk} withBorder radius="md" padding="lg">
                    <Group justify="space-between" align="flex-start">
                      <Stack gap={3}>
                        <Group gap="xs">
                          <Text fw={750}>{material.name}</Text>
                          {!material.active && <Badge color="gray">Paused</Badge>}
                          <Badge variant="outline">{material.currency}</Badge>
                        </Group>
                        <Text size="sm">
                          {formatQuantity(material.quantity)} ×{' '}
                          {formatMoney(material.unit_cost, material.currency, context.locale)} ={' '}
                          <strong>
                            {formatMoney(material.total_cost, material.currency, context.locale)}
                          </strong>
                        </Text>
                        {material.notes && (
                          <Text size="sm" c="dimmed">
                            {material.notes}
                          </Text>
                        )}
                      </Stack>
                      {data.permissions.change_purchase && (
                        <Group gap="xs">
                          <Button
                            size="xs"
                            variant="default"
                            onClick={() => openEditMaterial(material)}
                          >
                            Edit
                          </Button>
                          <Button
                            size="xs"
                            variant="default"
                            color="red"
                            onClick={() => askDeleteMaterial(material)}
                          >
                            Delete
                          </Button>
                        </Group>
                      )}
                    </Group>
                  </Card>
                ))
              )}
            </Stack>
          </Tabs.Panel>
        )}

        {data.permissions.view_sales && (
          <Tabs.Panel value="customers" pt="lg">
            <Stack gap="md">
              <Group justify="space-between" align="flex-start">
                <Stack gap={2}>
                  <Text fw={700}>Customer-specific schedules</Text>
                  <Text size="sm" c="dimmed">
                    Each customer can have its own currency and quantity breaks.
                  </Text>
                </Stack>
                {data.permissions.change_sales && (
                  <Button onClick={openNewList}>Add customer pricing</Button>
                )}
              </Group>

              {data.customer_lists.length === 0 ? (
                <EmptyState
                  title="No customer pricing yet"
                  message="Add a customer schedule to create quantity-specific pricing and synchronize native sale breaks."
                />
              ) : (
                data.customer_lists.map((priceList) => (
                  <Card key={priceList.pk} withBorder radius="md" padding="lg">
                    <Stack gap="md">
                      <Group justify="space-between" align="flex-start">
                        <Group gap="sm">
                          <Stack gap={1}>
                            <Group gap="xs">
                              <Text fw={750}>{priceList.customer_name}</Text>
                              <Badge color={priceList.active ? 'teal' : 'gray'} variant="light">
                                {priceList.active ? 'Active' : 'Paused'}
                              </Badge>
                              <Badge variant="outline">{priceList.currency}</Badge>
                              {priceList.profit_amount !== null && (
                                <Badge
                                  color={Number(priceList.profit_amount) >= 0 ? 'teal' : 'red'}
                                >
                                  {formatMoney(
                                    priceList.profit_amount,
                                    priceList.currency,
                                    context.locale
                                  )}{' '}
                                  profit
                                </Badge>
                              )}
                              {priceList.profit_margin_percent !== null && (
                                <Badge
                                  color={
                                    Number(priceList.profit_margin_percent) >= 0 ? 'teal' : 'red'
                                  }
                                  variant="light"
                                >
                                  {Number(priceList.profit_margin_percent).toFixed(2)}% margin
                                </Badge>
                              )}
                            </Group>
                            {priceList.notes && (
                              <Text size="sm" c="dimmed">
                                {priceList.notes}
                              </Text>
                            )}
                          </Stack>
                        </Group>
                        {data.permissions.change_sales && (
                          <Group gap="xs">
                            <Button
                              size="xs"
                              variant="default"
                              onClick={() => openEditList(priceList)}
                            >
                              Edit list
                            </Button>
                            <Button
                              size="xs"
                              variant="default"
                              color="red"
                              onClick={() => askDeleteList(priceList)}
                            >
                              Delete
                            </Button>
                          </Group>
                        )}
                      </Group>

                      <Divider />

                      <BreakTable
                        records={priceList.breaks}
                        currency={priceList.currency}
                        locale={context.locale}
                        editable={data.permissions.change_sales}
                        showMargin
                        onEdit={(record) =>
                          openBreakEditor(priceList.pk, priceList.currency, record)
                        }
                        onDelete={askDeleteBreak}
                      />

                      {data.permissions.change_sales && (
                        <Group justify="flex-end">
                          <Button
                            size="xs"
                            variant="light"
                            onClick={() =>
                              openBreakEditor(priceList.pk, priceList.currency)
                            }
                          >
                            Add quantity break
                          </Button>
                        </Group>
                      )}
                    </Stack>
                  </Card>
                ))
              )}
            </Stack>
          </Tabs.Panel>
        )}

      </Tabs>

      <Modal
        opened={materialEditor !== null}
        onClose={() => setMaterialEditor(null)}
        title={materialEditor?.record ? 'Edit material cost' : 'Add material cost'}
        centered
      >
        {materialEditor && (
          <Stack>
            <TextInput
              label="Material"
              placeholder="e.g. Aluminum sheet"
              required
              autoFocus
              value={materialEditor.name}
              onChange={(event) =>
                setMaterialEditor({ ...materialEditor, name: event.currentTarget.value })
              }
            />
            <SimpleGrid cols={2}>
              <NumberInput
                label="Quantity per part"
                required
                min={0.00001}
                decimalScale={5}
                value={materialEditor.quantity}
                onChange={(quantity) => setMaterialEditor({ ...materialEditor, quantity })}
              />
              <NumberInput
                label="Unit cost"
                required
                min={0}
                decimalScale={6}
                value={materialEditor.unitCost}
                onChange={(unitCost) => setMaterialEditor({ ...materialEditor, unitCost })}
              />
            </SimpleGrid>
            <Select
              label="Currency"
              searchable
              required
              data={data.currencies}
              value={materialEditor.currency}
              onChange={(currency) => setMaterialEditor({ ...materialEditor, currency })}
            />
            <Checkbox
              label="Include in material cost and margin calculations"
              checked={materialEditor.active}
              onChange={(event) =>
                setMaterialEditor({ ...materialEditor, active: event.currentTarget.checked })
              }
            />
            <Textarea
              label="Notes"
              placeholder="Optional grade, size, source, or calculation note"
              minRows={2}
              value={materialEditor.notes}
              onChange={(event) =>
                setMaterialEditor({ ...materialEditor, notes: event.currentTarget.value })
              }
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setMaterialEditor(null)}>
                Cancel
              </Button>
              <Button
                onClick={saveMaterial}
                disabled={
                  !materialEditor.name.trim() ||
                  materialEditor.quantity === '' ||
                  materialEditor.unitCost === '' ||
                  !materialEditor.currency
                }
              >
                Save material
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Modal
        opened={listEditor !== null}
        onClose={() => setListEditor(null)}
        title={listEditor?.record ? 'Edit customer price list' : 'Add customer pricing'}
        centered
      >
        {listEditor && (
          <Stack>
            {availableCustomers.length === 0 && !listEditor.record && (
              <Alert color="yellow" title="No available customers">
                Add or activate a customer in InvenTree, or remove its existing schedule for this
                part.
              </Alert>
            )}
            <Select
              label="Customer"
              placeholder="Choose a customer"
              searchable
              required
              data={availableCustomers}
              value={listEditor.customer}
              disabled={Boolean(listEditor.record)}
              onChange={(customer) => {
                const selected = data.customers.find(
                  (candidate) => candidate.pk === Number(customer)
                );
                setListEditor({
                  ...listEditor,
                  customer,
                  currency: listEditor.record
                    ? listEditor.currency
                    : selected?.currency || listEditor.currency
                });
              }}
            />
            <Select
              label="Currency"
              searchable
              required
              data={data.currencies}
              value={listEditor.currency}
              onChange={(currency) => setListEditor({ ...listEditor, currency })}
            />
            <Checkbox
              label="Active price list"
              description="Paused lists are retained but excluded from native synchronization."
              checked={listEditor.active}
              onChange={(event) =>
                setListEditor({ ...listEditor, active: event.currentTarget.checked })
              }
            />
            <Textarea
              label="Notes"
              placeholder="Optional pricing agreement or reference"
              minRows={3}
              value={listEditor.notes}
              onChange={(event) =>
                setListEditor({ ...listEditor, notes: event.currentTarget.value })
              }
            />
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setListEditor(null)}>
                Cancel
              </Button>
              <Button
                onClick={saveList}
                disabled={
                  !listEditor.customer ||
                  !listEditor.currency ||
                  (!listEditor.record && availableCustomers.length === 0)
                }
              >
                Save price list
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Modal
        opened={breakEditor !== null}
        onClose={() => setBreakEditor(null)}
        title={breakEditor?.record ? 'Edit price break' : 'Add price break'}
        centered
      >
        {breakEditor && (
          <Stack>
            <NumberInput
              label="Minimum quantity"
              required
              min={1}
              decimalScale={5}
              value={breakEditor.quantity}
              onChange={(quantity) => setBreakEditor({ ...breakEditor, quantity })}
            />
            <NumberInput
              label="Unit price"
              required
              min={0}
              decimalScale={6}
              value={breakEditor.price}
              onChange={(price) => setBreakEditor({ ...breakEditor, price })}
            />
            <Select
              label="Currency"
              searchable
              required
              data={data.currencies}
              value={breakEditor.currency}
              disabled
              onChange={(currency) => setBreakEditor({ ...breakEditor, currency })}
            />
            <Text size="xs" c="dimmed">
              Customer tiers use the currency configured on their price list.
            </Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setBreakEditor(null)}>
                Cancel
              </Button>
              <Button
                onClick={saveBreak}
                disabled={
                  breakEditor.price === '' || breakEditor.quantity === '' || !breakEditor.currency
                }
              >
                Save price break
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>

      <Modal
        opened={confirmation !== null}
        onClose={() => setConfirmation(null)}
        title={confirmation?.title}
        centered
        size="sm"
      >
        {confirmation && (
          <Stack>
            <Text size="sm">{confirmation.message}</Text>
            <Group justify="flex-end">
              <Button variant="default" onClick={() => setConfirmation(null)}>
                Cancel
              </Button>
              <Button
                color="red"
                onClick={async () => {
                  await confirmation.action();
                  setConfirmation(null);
                }}
              >
                Delete
              </Button>
            </Group>
          </Stack>
        )}
      </Modal>
    </Stack>
  );
}

export function RenderCustomerPricingPluginPanel(context: PricingPluginContext) {
  return <CustomerPricingPanel context={context} />;
}

type MobileSummary = {
  title: string;
  description: string;
  sections: {
    title: string;
    items: { label: string; value: string; detail?: string }[];
  }[];
};

function PartPricingDashboard({ context }: { context: PricingPluginContext }) {
  const [summary, setSummary] = useState<MobileSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    context.api
      .get<MobileSummary>('/plugin/customer-pricing/mobile/dashboard/')
      .then((response) => setSummary(response.data))
      .catch((requestError) => setError(apiErrorMessage(requestError)));
  }, [context.api]);

  if (error) {
    return (
      <Alert color="red" title="Part Pricing could not load">
        {error}
      </Alert>
    );
  }

  if (!summary) {
    return (
      <Paper pos="relative" mih={140}>
        <LoadingOverlay visible />
      </Paper>
    );
  }

  const overview = summary.sections.find((section) => section.title === 'Overview');

  return (
    <Stack gap="sm">
      <Stack gap={1}>
        <Text fw={750}>{summary.title}</Text>
        <Text size="sm" c="dimmed">
          {summary.description}
        </Text>
      </Stack>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        {overview?.items.map((item) => (
          <Paper key={item.label} withBorder p="sm" radius="md">
            <Text size="xs" c="dimmed">
              {item.label}
            </Text>
            <Text fw={750} fz="xl">
              {item.value}
            </Text>
          </Paper>
        ))}
      </SimpleGrid>
      <Text size="xs" c="dimmed">
        Open any part to edit material costs and view customer margins.
      </Text>
    </Stack>
  );
}

export function RenderPartPricingDashboard(context: PricingPluginContext) {
  return <PartPricingDashboard context={context} />;
}
