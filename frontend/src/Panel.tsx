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
  Switch,
  Table,
  Tabs,
  Text,
  Textarea,
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
    get: (url: string) => Promise<{ data: WorkspaceData }>;
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
};

type CustomerPriceList = {
  pk: number;
  part: number;
  customer: number;
  customer_name: string;
  currency: string;
  active: boolean;
  notes: string;
  breaks: CustomerBreak[];
  created: string;
  updated: string;
};

type SupplierPart = {
  pk: number;
  supplier: number;
  supplier_name: string;
  sku: string;
  active: boolean;
  primary: boolean;
  breaks: NativeBreak[];
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
    sync_native_sale: boolean;
    sync_currency: string;
    resolved_currency: string;
    last_synced: string | null;
    last_sync_error: string;
  };
  customer_lists: CustomerPriceList[];
  customers: { pk: number; name: string; currency: string }[];
  native_sale_breaks: NativeBreak[];
  supplier_parts: SupplierPart[];
  currencies: string[];
};

type ListEditorState = {
  record?: CustomerPriceList;
  customer: string | null;
  currency: string | null;
  active: boolean;
  notes: string;
};

type BreakKind = 'customer' | 'sale' | 'purchase';

type BreakEditorState = {
  kind: BreakKind;
  ownerId?: number;
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
      maximumFractionDigits: 6
    }).format(Number(value));
  } catch {
    return `${currency} ${value}`;
  }
}

function formatQuantity(value: string): string {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 5 });
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
  onEdit,
  onDelete
}: {
  records: (NativeBreak | CustomerBreak)[];
  currency: string;
  locale: string;
  editable: boolean;
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
            {editable && <Table.Th ta="right">Actions</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {records.map((record) => (
            <Table.Tr key={record.pk}>
              <Table.Td fw={600}>{formatQuantity(record.quantity)}</Table.Td>
              <Table.Td>{formatMoney(record.price, record.currency || currency, locale)}</Table.Td>
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
          ))}
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

  const availableCustomers = useMemo(() => {
    if (!data) {
      return [];
    }

    const currentCustomer = listEditor?.record?.customer;
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

    const payload = {
      customer: Number(listEditor.customer),
      currency: listEditor.currency,
      active: listEditor.active,
      notes: listEditor.notes
    };
    const url = listEditor.record
      ? `${apiBase}/customer-lists/${listEditor.record.pk}/`
      : `${apiBase}/customer-lists/`;

    await request(
      listEditor.record ? 'patch' : 'post',
      url,
      payload,
      listEditor.record ? 'Customer price list saved.' : 'Customer price list created.'
    );
    setListEditor(null);
  };

  const openBreakEditor = (
    kind: BreakKind,
    ownerId: number | undefined,
    currency: string,
    record?: NativeBreak | CustomerBreak
  ) => {
    setBreakEditor({
      kind,
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

    const basePayload = {
      quantity: breakEditor.quantity,
      price: breakEditor.price
    };
    let url = '';
    let payload: Record<string, unknown> = basePayload;

    if (breakEditor.kind === 'customer') {
      url = breakEditor.record
        ? `${apiBase}/customer-breaks/${breakEditor.record.pk}/`
        : `${apiBase}/customer-lists/${breakEditor.ownerId}/breaks/`;
    } else if (breakEditor.kind === 'sale') {
      url = breakEditor.record
        ? `${apiBase}/sale-breaks/${breakEditor.record.pk}/`
        : `${apiBase}/sale-breaks/`;
      payload = { ...basePayload, currency: breakEditor.currency };
    } else {
      url = breakEditor.record
        ? `${apiBase}/supplier-breaks/${breakEditor.record.pk}/`
        : `${apiBase}/supplier-parts/${breakEditor.ownerId}/breaks/`;
      payload = { ...basePayload, currency: breakEditor.currency };
    }

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
      message: `This removes every ${record.customer_name} price break for this part. Native sale pricing will be synchronized immediately.`,
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

  const askDeleteBreak = (kind: BreakKind, record: NativeBreak | CustomerBreak) => {
    const segment =
      kind === 'customer' ? 'customer-breaks' : kind === 'sale' ? 'sale-breaks' : 'supplier-breaks';
    setConfirmation({
      title: 'Delete price break?',
      message: `The quantity ${formatQuantity(record.quantity)} price break will be removed.`,
      action: async () => {
        await request(
          'delete',
          `${apiBase}/${segment}/${record.pk}/`,
          undefined,
          'Price break deleted.'
        );
      }
    });
  };

  const updatePolicy = async (payload: Record<string, unknown>) => {
    await request('patch', `${apiBase}/policy/`, payload, 'Synchronization policy saved.');
  };

  const defaultTab = data?.permissions.view_sales ? 'customers' : 'purchase';

  if (loading) {
    return (
      <Paper pos="relative" mih={240}>
        <LoadingOverlay visible />
      </Paper>
    );
  }

  if (error || !data) {
    return (
      <Alert color="red" title="Customer Pricing could not load">
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
        <Group justify="space-between" align="flex-start">
          <Stack gap={3}>
            <Text size="xs" fw={700} tt="uppercase" opacity={0.8}>
              Pricing workspace
            </Text>
            <Title order={3}>{data.part.ipn || data.part.name}</Title>
            <Text size="sm" opacity={0.9}>
              Purchase, sale, and customer pricing in one place
            </Text>
          </Stack>
          <Badge color={data.policy.sync_native_sale ? 'teal' : 'gray'} variant="filled" size="lg">
            {data.policy.sync_native_sale ? 'Native sync active' : 'Manual sale pricing'}
          </Badge>
        </Group>
      </Paper>

      {data.permissions.view_sales && (
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <MetricCard
            label="Priced customers"
            value={String(data.customer_lists.length)}
            detail={`${data.customer_lists.filter((priceList) => priceList.active).length} active schedules`}
          />
          <MetricCard
            label="Customer tiers"
            value={String(customerTierCount)}
            detail="Across all customer schedules"
          />
          <MetricCard
            label="Native sale tiers"
            value={String(data.native_sale_breaks.length)}
            detail={`Synchronized in ${data.policy.resolved_currency}`}
          />
        </SimpleGrid>
      )}

      <Tabs defaultValue={defaultTab} keepMounted={false}>
        <Tabs.List>
          {data.permissions.view_sales && <Tabs.Tab value="customers">Customer pricing</Tabs.Tab>}
          {data.permissions.view_sales && <Tabs.Tab value="sale">Sale pricing</Tabs.Tab>}
          {data.permissions.view_purchase && <Tabs.Tab value="purchase">Purchase pricing</Tabs.Tab>}
        </Tabs.List>

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
                        onEdit={(record) =>
                          openBreakEditor('customer', priceList.pk, priceList.currency, record)
                        }
                        onDelete={(record) => askDeleteBreak('customer', record)}
                      />

                      {data.permissions.change_sales && (
                        <Group justify="flex-end">
                          <Button
                            size="xs"
                            variant="light"
                            onClick={() =>
                              openBreakEditor('customer', priceList.pk, priceList.currency)
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

        {data.permissions.view_sales && (
          <Tabs.Panel value="sale" pt="lg">
            <Stack gap="md">
              <Card withBorder radius="md" padding="lg">
                <Stack gap="md">
                  <Group justify="space-between" align="flex-start">
                    <Stack gap={2}>
                      <Text fw={700}>Native sale pricing sync</Text>
                      <Text size="sm" c="dimmed" maw={720}>
                        When enabled, every customer quantity boundary is evaluated and the highest
                        applicable customer price is written to InvenTree's native sale-price table.
                      </Text>
                    </Stack>
                    {data.permissions.change_sales && (
                      <Button
                        size="xs"
                        variant="light"
                        disabled={!data.policy.sync_native_sale}
                        onClick={() =>
                          request(
                            'post',
                            `${apiBase}/sync/`,
                            undefined,
                            'Native sale prices synchronized.'
                          )
                        }
                      >
                        Sync now
                      </Button>
                    )}
                  </Group>

                  {data.policy.last_sync_error && (
                    <Alert color="red" title="Last synchronization failed">
                      {data.policy.last_sync_error}
                    </Alert>
                  )}

                  <SimpleGrid cols={{ base: 1, sm: 2 }}>
                    <Switch
                      label="Automatically synchronize native sale pricing"
                      description="Customer pricing is authoritative while enabled."
                      checked={data.policy.sync_native_sale}
                      disabled={!data.permissions.change_sales}
                      onChange={(event) =>
                        updatePolicy({ sync_native_sale: event.currentTarget.checked })
                      }
                    />
                    <Select
                      label="Native synchronization currency"
                      description="Different customer currencies are converted before comparison."
                      searchable
                      clearable
                      placeholder={data.policy.resolved_currency}
                      value={data.policy.sync_currency || null}
                      data={data.currencies}
                      disabled={!data.permissions.change_sales}
                      onChange={(value) => updatePolicy({ sync_currency: value || '' })}
                    />
                  </SimpleGrid>

                  <Text size="xs" c="dimmed">
                    {data.policy.last_synced
                      ? `Last synchronized ${new Intl.DateTimeFormat(context.locale || 'en', {
                          dateStyle: 'medium',
                          timeStyle: 'short'
                        }).format(new Date(data.policy.last_synced))}`
                      : 'Native pricing has not been synchronized by this plugin yet.'}
                  </Text>
                </Stack>
              </Card>

              <Card withBorder radius="md" padding="lg">
                <Stack gap="md">
                  <Group justify="space-between">
                    <Stack gap={2}>
                      <Text fw={700}>InvenTree sale-price breaks</Text>
                      <Text size="sm" c="dimmed">
                        {data.policy.sync_native_sale
                          ? 'Read-only here because these rows are managed by customer pricing.'
                          : 'Automatic sync is off; these native rows can be edited manually.'}
                      </Text>
                    </Stack>
                    {data.permissions.change_sales && !data.policy.sync_native_sale && (
                      <Button
                        size="xs"
                        onClick={() =>
                          openBreakEditor('sale', undefined, data.policy.resolved_currency)
                        }
                      >
                        Add sale break
                      </Button>
                    )}
                  </Group>

                  <BreakTable
                    records={data.native_sale_breaks}
                    currency={data.policy.resolved_currency}
                    locale={context.locale}
                    editable={data.permissions.change_sales && !data.policy.sync_native_sale}
                    onEdit={(record) => openBreakEditor('sale', undefined, record.currency, record)}
                    onDelete={(record) => askDeleteBreak('sale', record)}
                  />
                </Stack>
              </Card>
            </Stack>
          </Tabs.Panel>
        )}

        {data.permissions.view_purchase && (
          <Tabs.Panel value="purchase" pt="lg">
            <Stack gap="md">
              <Stack gap={2}>
                <Text fw={700}>Native supplier pricing</Text>
                <Text size="sm" c="dimmed">
                  These price breaks are stored directly on InvenTree supplier parts.
                </Text>
              </Stack>

              {data.supplier_parts.length === 0 ? (
                <EmptyState
                  title="No supplier parts found"
                  message="Add a supplier part from the Suppliers tab before entering purchase price breaks."
                />
              ) : (
                data.supplier_parts.map((supplierPart) => (
                  <Card key={supplierPart.pk} withBorder radius="md" padding="lg">
                    <Stack gap="md">
                      <Group justify="space-between" align="flex-start">
                        <Stack gap={1}>
                          <Group gap="xs">
                            <Text fw={750}>{supplierPart.supplier_name}</Text>
                            {supplierPart.primary && <Badge variant="light">Primary</Badge>}
                            {!supplierPart.active && <Badge color="gray">Inactive</Badge>}
                          </Group>
                          <Text size="sm" c="dimmed">
                            SKU {supplierPart.sku}
                          </Text>
                        </Stack>
                        {data.permissions.change_purchase && (
                          <Button
                            size="xs"
                            variant="light"
                            onClick={() =>
                              openBreakEditor(
                                'purchase',
                                supplierPart.pk,
                                supplierPart.breaks[0]?.currency || data.policy.resolved_currency
                              )
                            }
                          >
                            Add purchase break
                          </Button>
                        )}
                      </Group>

                      <Divider />

                      <BreakTable
                        records={supplierPart.breaks}
                        currency={supplierPart.breaks[0]?.currency || data.policy.resolved_currency}
                        locale={context.locale}
                        editable={data.permissions.change_purchase}
                        onEdit={(record) =>
                          openBreakEditor('purchase', supplierPart.pk, record.currency, record)
                        }
                        onDelete={(record) => askDeleteBreak('purchase', record)}
                      />
                    </Stack>
                  </Card>
                ))
              )}
            </Stack>
          </Tabs.Panel>
        )}
      </Tabs>

      <Modal
        opened={listEditor !== null}
        onClose={() => setListEditor(null)}
        title={listEditor?.record ? 'Edit customer price list' : 'Add customer pricing'}
        centered
      >
        {listEditor && (
          <Stack>
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
              <Button onClick={saveList} disabled={!listEditor.customer || !listEditor.currency}>
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
              disabled={breakEditor.kind === 'customer'}
              onChange={(currency) => setBreakEditor({ ...breakEditor, currency })}
            />
            {breakEditor.kind === 'customer' && (
              <Text size="xs" c="dimmed">
                Customer tiers use the currency configured on their price list.
              </Text>
            )}
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
