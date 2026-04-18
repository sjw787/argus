import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/v1/auth/config', () =>
    HttpResponse.json({ mode: 'none', streaming: false })
  ),

  http.get('/api/v1/auth/status', () =>
    HttpResponse.json({
      authenticated: true,
      profile: 'test-user',
      profiles: ['test-user'],
    })
  ),

  http.get('/api/v1/config', () =>
    HttpResponse.json({
      region: 'us-east-1',
      workgroup_output_locations: {},
      max_results: 1000,
      query_timeout_seconds: 300,
      locked_settings: [],
      allow_download: true,
    })
  ),

  http.get('/api/v1/catalog/databases', () =>
    HttpResponse.json({
      items: [{ name: 'test_db', description: '', parameters: {}, workgroup: null }],
      total: 1,
      offset: 0,
      limit: 50,
      has_more: false,
    })
  ),

  http.get('/api/v1/catalog/databases/:dbName', () =>
    HttpResponse.json({ name: 'test_db', description: '', parameters: {}, workgroup: null })
  ),

  http.get('/api/v1/catalog/databases/:dbName/tables', () =>
    HttpResponse.json([
      { name: 'users', database_name: 'test_db', table_type: 'EXTERNAL_TABLE', columns: [] },
    ])
  ),

  http.get('/api/v1/catalog/databases/:dbName/tables/:tableName', () =>
    HttpResponse.json({
      name: 'users',
      database_name: 'test_db',
      table_type: 'EXTERNAL_TABLE',
      columns: [{ name: 'id', type: 'int', comment: '' }],
      parameters: {},
      partition_keys: [],
    })
  ),

  http.get('/api/v1/catalog/databases/:dbName/tables/:tableName/partitions', () =>
    HttpResponse.json([])
  ),

  http.get('/api/v1/catalog/databases/:dbName/er-diagram', () =>
    HttpResponse.json({ tables: [], relationships: [] })
  ),

  http.get('/api/v1/workgroups', () =>
    HttpResponse.json([{ name: 'primary' }])
  ),

  http.get('/api/v1/workgroups/names', () =>
    HttpResponse.json(['primary'])
  ),

  http.get('/api/v1/config/assignments', () =>
    HttpResponse.json({ assignments: {} })
  ),

  http.get('/api/v1/queries', () =>
    HttpResponse.json([])
  ),

  http.get('/api/v1/queries/named/list', () =>
    HttpResponse.json([])
  ),

  http.post('/api/v1/queries/execute', () =>
    HttpResponse.json({ query_execution_id: 'test-query-id', limit_applied: false })
  ),

  http.get('/api/v1/queries/test-query-id', () =>
    HttpResponse.json({
      query_execution_id: 'test-query-id',
      query: 'SELECT 1',
      status: { state: 'SUCCEEDED' },
      stats: {},
    })
  ),

  http.get('/api/v1/queries/test-query-id/status', () =>
    HttpResponse.json({ execution_id: 'test-query-id', state: 'SUCCEEDED' })
  ),

  http.get('/api/v1/queries/test-query-id/results', () =>
    HttpResponse.json({ columns: [], rows: [], next_token: null, row_count: 0 })
  ),
]
