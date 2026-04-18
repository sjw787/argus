import axios from 'axios'
import { useAuthStore } from '../stores/authStore'

export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Intercept 401 auth_expired errors and trigger the session-expired flow
apiClient.interceptors.response.use(
  res => res,
  err => {
    if (err?.response?.status === 401 && err?.response?.data?.error_type === 'auth_expired') {
      const store = useAuthStore.getState()
      // Ignore stale 401s that arrive within 5s of a fresh login (avoids re-triggering the loop)
      const msSinceAuth = Date.now() - store.lastAuthTime
      if (store.authenticated && msSinceAuth > 5000) {
        store.setSessionExpired(true)
      }
    }
    return Promise.reject(err)
  }
)

// Inject X-Credential-Id header for Lambda SSO mode
apiClient.interceptors.request.use(config => {
  const credentialId = useAuthStore.getState().credentialId
  if (credentialId) {
    config.headers['X-Credential-Id'] = credentialId
  }
  return config
})

// Types matching the backend Pydantic schemas
export interface ExecuteQueryRequest {
  sql: string
  database: string
  workgroup?: string
  output_location?: string
  schema_name?: string
  auto_limit?: number
}

export interface ExecuteQueryResponse {
  query_execution_id: string
  limit_applied: boolean
}

export interface QueryStatus {
  state: string
  state_change_reason?: string
  submission_datetime?: string
  completion_datetime?: string
}

export interface QueryStats {
  data_scanned_bytes?: number
  total_execution_time_ms?: number
}

export interface QueryExecutionDetail {
  query_execution_id: string
  query: string
  database?: string
  workgroup?: string
  status: QueryStatus
  stats: QueryStats
  output_location?: string
}

export interface QueryStatusSnapshot {
  execution_id: string
  state: string
  state_change_reason?: string
  query?: string
  submitted_at?: string
  completed_at?: string
}

export interface AuthConfig {
  mode: 'sso' | 'cognito' | 'none'
  streaming: boolean
  cognitoUserPoolId?: string
  cognitoClientId?: string
  cognitoDomain?: string
}

export interface ResultColumn {
  name: string
  type?: string
}

export interface QueryResults {
  columns: ResultColumn[]
  rows: (string | null)[][]
  next_token?: string
  row_count: number
}

export interface QueryListItem {
  query_execution_id: string
  database?: string
  workgroup?: string
  state: string
  submitted?: string
}

export interface DatabaseItem {
  name: string
  description?: string
  location_uri?: string
  parameters: Record<string, string>
  workgroup?: string
}

export interface PaginatedDatabaseResponse {
  items: DatabaseItem[]
  total: number
  offset: number
  limit: number
  has_more: boolean
}

export interface ListDatabasesParams {
  catalogId?: string
  search?: string
  limit?: number
  offset?: number
}

export interface ColumnItem {
  name: string
  type: string
  comment?: string
}

export interface TableSummary {
  name: string
  table_type?: string
  location?: string
  created_time?: string
}

export interface TableItem {
  name: string
  database_name: string
  table_type?: string
  location?: string
  input_format?: string
  output_format?: string
  created_time?: string
  updated_time?: string
  columns: ColumnItem[]
  partition_keys: ColumnItem[]
  parameters: Record<string, string>
}

export interface PartitionItem {
  values: string[]
  location?: string
  created_time?: string
}

export interface ErNode {
  id: string
  name: string
  columns: ColumnItem[]
  partition_keys: ColumnItem[]
}

export interface ErEdge {
  source_table: string
  source_column: string
  target_table: string
  target_column: string
}

export interface ErDiagramData {
  nodes: ErNode[]
  edges: ErEdge[]
}

export interface WorkgroupItem {
  name: string
  state?: string
  description?: string
  output_location?: string
  engine_version?: string
  created_time?: string
}

export interface ConfigInfo {
  region: string
  profile?: string
  workgroup_output_locations: Record<string, string>
  default_output_location?: string
  max_results: number
  query_timeout_seconds: number
  locked_settings: string[]
  allow_download: boolean
}

// Auth / SSO types
export interface AuthStatus {
  authenticated: boolean
  profile?: string
  region?: string
  profiles: string[]
}

export interface SsoStartResponse {
  session_id: string
  user_code: string
  verification_uri: string
  verification_uri_complete: string
  expires_in: number
  interval: number
}

export interface SsoPollResponse {
  status: 'pending' | 'success' | 'expired' | 'denied'
  access_token?: string
}

export interface SsoAccount {
  account_id: string
  account_name: string
  email: string
}

export interface SsoRole {
  account_id: string
  role_name: string
}

export interface SsoSelectRoleResponse {
  profile_name: string
  expiration: string
  message: string
  credential_id?: string  // Lambda mode: send as X-Credential-Id header
}

// API functions
export const api = {
  // Queries
  executeQuery: (data: ExecuteQueryRequest) =>
    apiClient.post<ExecuteQueryResponse>('/queries/execute', data).then(r => r.data),

  getQuery: (id: string) =>
    apiClient.get<QueryExecutionDetail>(`/queries/${id}`).then(r => r.data),

  getQueryResults: (id: string, pageSize = 100, nextToken?: string) =>
    apiClient.get<QueryResults>(`/queries/${id}/results`, {
      params: { page_size: pageSize, next_token: nextToken },
    }).then(r => r.data),

  cancelQuery: (id: string) =>
    apiClient.post(`/queries/${id}/cancel`).then(r => r.data),

  listQueries: (workgroup?: string, limit = 20) =>
    apiClient.get<QueryListItem[]>('/queries', { params: { workgroup, limit } }).then(r => r.data),

  listNamedQueries: (workgroup?: string) =>
    apiClient.get('/queries/named/list', { params: { workgroup } }).then(r => r.data),

  // Catalog
  listDatabases: (params?: ListDatabasesParams) =>
    apiClient.get<PaginatedDatabaseResponse>('/catalog/databases', {
      params: {
        catalog_id: params?.catalogId,
        search: params?.search || undefined,
        limit: params?.limit ?? 50,
        offset: params?.offset ?? 0,
      }
    }).then(r => r.data),

  getDatabase: (name: string) =>
    apiClient.get<DatabaseItem>(`/catalog/databases/${name}`).then(r => r.data),

  createDatabase: (data: { name: string; description?: string; location_uri?: string }) =>
    apiClient.post<DatabaseItem>('/catalog/databases', data).then(r => r.data),

  deleteDatabase: (name: string) =>
    apiClient.delete(`/catalog/databases/${name}`).then(r => r.data),

  listTables: (dbName: string, expression?: string) =>
    apiClient.get<TableSummary[]>(`/catalog/databases/${dbName}/tables`, { params: { expression } }).then(r => r.data),

  getTable: (dbName: string, tableName: string) =>
    apiClient.get<TableItem>(`/catalog/databases/${dbName}/tables/${tableName}`).then(r => r.data),

  deleteTable: (dbName: string, tableName: string) =>
    apiClient.delete(`/catalog/databases/${dbName}/tables/${tableName}`).then(r => r.data),

  listPartitions: (dbName: string, tableName: string, expression?: string) =>
    apiClient.get<PartitionItem[]>(`/catalog/databases/${dbName}/tables/${tableName}/partitions`, { params: { expression } }).then(r => r.data),

  getErDiagram: (dbName: string) =>
    apiClient.get<ErDiagramData>(`/catalog/databases/${dbName}/er-diagram`).then(r => r.data),

  // Workgroups
  listWorkgroups: () =>
    apiClient.get<WorkgroupItem[]>('/workgroups').then(r => r.data),

  // Config
  getConfig: () =>
    apiClient.get<ConfigInfo>('/config').then(r => r.data),

  getAssignments: () =>
    apiClient.get<{ assignments: Record<string, string> }>('/config/assignments').then(r => r.data),

  listWorkgroupNames: () =>
    apiClient.get<string[]>('/workgroups/names').then(r => r.data),

  createWorkgroup: (data: { name: string; description?: string; output_location?: string; engine_version?: string }) =>
    apiClient.post<WorkgroupItem>('/workgroups', data).then(r => r.data),

  deleteWorkgroup: (name: string, recursive = false) =>
    apiClient.delete(`/workgroups/${name}`, { params: { recursive } }).then(r => r.data),

  validateS3Location: (location: string) =>
    apiClient.post<{ valid: boolean; bucket?: string; prefix?: string; error?: string }>('/workgroups/validate-s3', { location }).then(r => r.data),

  assignDatabase: (database: string, workgroup: string) =>
    apiClient.post<{ assignments: Record<string, string> }>('/config/assignments', { database, workgroup }).then(r => r.data),

  unassignDatabase: (database: string) =>
    apiClient.delete<{ assignments: Record<string, string> }>(`/config/assignments/${database}`).then(r => r.data),

  // Export
  exportResults: (queryId: string, format: string, delimiter = ',', pretty = false) =>
    apiClient.post(`/export/${queryId}`, { format, delimiter, pretty }, { responseType: 'blob' }).then(r => r.data),

  // Auth / SSO
  getAuthStatus: (profile?: string, region?: string) =>
    apiClient.get<AuthStatus>('/auth/status', { params: { profile, region } }).then(r => r.data),

  listProfiles: () =>
    apiClient.get<string[]>('/auth/profiles').then(r => r.data),

  selectProfile: (profileName: string, region?: string) =>
    apiClient.post<AuthStatus>('/auth/profile/select', { profile_name: profileName }, { params: { region } }).then(r => r.data),

  ssoStart: (startUrl: string, region: string) =>
    apiClient.post<SsoStartResponse>('/auth/sso/start', { start_url: startUrl, region }).then(r => r.data),

  ssoPoll: (sessionId: string) =>
    apiClient.get<SsoPollResponse>(`/auth/sso/poll/${sessionId}`).then(r => r.data),

  ssoListAccounts: (sessionId: string) =>
    apiClient.get<SsoAccount[]>(`/auth/sso/${sessionId}/accounts`).then(r => r.data),

  ssoListRoles: (sessionId: string, accountId: string) =>
    apiClient.get<SsoRole[]>(`/auth/sso/${sessionId}/accounts/${accountId}/roles`).then(r => r.data),

  ssoSelectRole: (sessionId: string, accountId: string, roleName: string, profileName: string) =>
    apiClient.post<SsoSelectRoleResponse>('/auth/sso/select-role', {
      session_id: sessionId,
      account_id: accountId,
      role_name: roleName,
      profile_name: profileName,
    }).then(r => r.data),

  getSsoConfig: () =>
    apiClient.get<{ start_url?: string; region?: string; profile?: string }>('/auth/sso-config').then(r => r.data),

  getQueryStatus: (id: string) =>
    apiClient.get<QueryStatusSnapshot>(`/queries/${id}/status`).then(r => r.data),

  getAuthConfig: (): Promise<AuthConfig> =>
    apiClient.get<{ mode: string; streaming: boolean; cognito_user_pool_id?: string; cognito_client_id?: string; cognito_domain?: string }>('/auth/config')
      .then(r => ({
        mode: r.data.mode as AuthConfig['mode'],
        streaming: r.data.streaming,
        cognitoUserPoolId: r.data.cognito_user_pool_id,
        cognitoClientId: r.data.cognito_client_id,
        cognitoDomain: r.data.cognito_domain,
      })),

  signOut: () =>
    apiClient.post<{ ok: boolean }>('/auth/logout').then(r => r.data),
}
