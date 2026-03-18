import { useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { 
  Database, 
  Zap, 
  CheckCircle, 
  AlertTriangle, 
  Clock, 
  Play, 
  Pause,
  RefreshCw,
  Settings,
  Terminal,
  FileCode,
  ArrowRight
} from 'lucide-react'

// Mock data
const mockRuns = [
  { id: 'run_20240318_001', phase: 'optimize', progress: 65, sqlCount: 12, issues: 3, date: '2024-03-18' },
  { id: 'run_20240317_002', phase: 'completed', progress: 100, sqlCount: 8, issues: 5, date: '2024-03-17' },
  { id: 'run_20240316_003', phase: 'validate', progress: 80, sqlCount: 15, issues: 2, date: '2024-03-16' },
]

const mockSqlUnits = [
  { key: 'UserMapper.selectById', risk: 'HIGH', branches: 4, status: 'pending' },
  { key: 'UserMapper.listUsers', risk: 'MEDIUM', branches: 2, status: 'analyzed' },
  { key: 'OrderMapper.findByCondition', risk: 'HIGH', branches: 8, status: 'optimized' },
  { key: 'ProductMapper.search', risk: 'LOW', branches: 1, status: 'completed' },
]

const mockProposals = [
  { id: 'prop_001', sqlKey: 'UserMapper.selectById', suggestion: 'Add index on (id, status)', impact: 'HIGH', accepted: true },
  { id: 'prop_002', sqlKey: 'UserMapper.listUsers', suggestion: 'Use LIMIT for pagination', impact: 'MEDIUM', accepted: false },
  { id: 'prop_003', sqlKey: 'OrderMapper.findByCondition', suggestion: 'Rewrite subquery as JOIN', impact: 'HIGH', accepted: true },
]

function App() {
  const [selectedRun, setSelectedRun] = useState(mockRuns[0])

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
              <Database className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">SQL Optimizer</h1>
              <p className="text-xs text-slate-500">MyBatis SQL Analysis & Optimization</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm">
              <Terminal className="w-4 h-4 mr-2" />
              CLI
            </Button>
            <Button variant="outline" size="sm">
              <Settings className="w-4 h-4 mr-2" />
              Settings
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <Tabs defaultValue="dashboard" className="space-y-6">
          <TabsList>
            <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
            <TabsTrigger value="runs">Runs</TabsTrigger>
            <TabsTrigger value="analysis">Analysis</TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard" className="space-y-6">
            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-500">Total Runs</p>
                      <p className="text-2xl font-bold">24</p>
                    </div>
                    <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                      <Database className="w-6 h-6 text-blue-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-500">SQL Analyzed</p>
                      <p className="text-2xl font-bold">156</p>
                    </div>
                    <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center">
                      <CheckCircle className="w-6 h-6 text-green-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-500">Issues Found</p>
                      <p className="text-2xl font-bold">42</p>
                    </div>
                    <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center">
                      <AlertTriangle className="w-6 h-6 text-amber-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-slate-500">Optimized</p>
                      <p className="text-2xl font-bold">89%</p>
                    </div>
                    <div className="w-12 h-12 bg-purple-100 rounded-full flex items-center justify-center">
                      <Zap className="w-6 h-6 text-purple-600" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Current Run */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Play className="w-5 h-5 text-blue-600" />
                  Current Run
                </CardTitle>
                <CardDescription>{selectedRun.id}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between text-sm">
                  <span>Phase: <Badge variant="outline">{selectedRun.phase}</Badge></span>
                  <span>{selectedRun.progress}%</span>
                </div>
                <Progress value={selectedRun.progress} className="h-2" />
                <div className="flex gap-4 text-sm text-slate-500">
                  <span>SQLs: {selectedRun.sqlCount}</span>
                  <span>Issues: {selectedRun.issues}</span>
                  <span>{selectedRun.date}</span>
                </div>
              </CardContent>
              <CardFooter className="gap-2">
                <Button size="sm">
                  <Pause className="w-4 h-4 mr-1" />
                  Pause
                </Button>
                <Button size="sm" variant="outline">
                  <RefreshCw className="w-4 h-4 mr-1" />
                  Resume
                </Button>
              </CardFooter>
            </Card>

            {/* Recent Runs */}
            <Card>
              <CardHeader>
                <CardTitle>Recent Runs</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run ID</TableHead>
                      <TableHead>Phase</TableHead>
                      <TableHead>Progress</TableHead>
                      <TableHead>SQLs</TableHead>
                      <TableHead>Issues</TableHead>
                      <TableHead>Date</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockRuns.map((run) => (
                      <TableRow 
                        key={run.id} 
                        className="cursor-pointer hover:bg-slate-50"
                        onClick={() => setSelectedRun(run)}
                      >
                        <TableCell className="font-mono text-sm">{run.id}</TableCell>
                        <TableCell>
                          <Badge variant={run.phase === 'completed' ? 'default' : 'secondary'}>
                            {run.phase}
                          </Badge>
                        </TableCell>
                        <TableCell>{run.progress}%</TableCell>
                        <TableCell>{run.sqlCount}</TableCell>
                        <TableCell>
                          <span className={run.issues > 3 ? 'text-amber-600' : ''}>
                            {run.issues}
                          </span>
                        </TableCell>
                        <TableCell className="text-slate-500">{run.date}</TableCell>
                        <TableCell>
                          <Button size="sm" variant="ghost">
                            <ArrowRight className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="runs" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>SQL Units</CardTitle>
                <CardDescription>All SQL statements discovered in this run</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>SQL Key</TableHead>
                      <TableHead>Risk Level</TableHead>
                      <TableHead>Branches</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {mockSqlUnits.map((sql) => (
                      <TableRow key={sql.key}>
                        <TableCell className="font-mono text-sm">{sql.key}</TableCell>
                        <TableCell>
                          <Badge variant={sql.risk === 'HIGH' ? 'destructive' : sql.risk === 'MEDIUM' ? 'secondary' : 'secondary'}>
                            {sql.risk}
                          </Badge>
                        </TableCell>
                        <TableCell>{sql.branches}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{sql.status}</Badge>
                        </TableCell>
                        <TableCell>
                          <Button size="sm" variant="ghost">
                            <FileCode className="w-4 h-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="analysis" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Optimization Proposals</CardTitle>
                <CardDescription>LLM-generated optimization suggestions</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                    {mockProposals.map((prop) => (
                      <Alert key={prop.id}>
                        <AlertTitle className="flex items-center justify-between">
                          <span className="font-mono text-sm">{prop.sqlKey}</span>
                          <Badge>{prop.impact}</Badge>
                        </AlertTitle>
                      <AlertDescription className="flex items-center justify-between mt-2">
                        <span>{prop.suggestion}</span>
                        {prop.accepted ? (
                          <CheckCircle className="w-4 h-4 text-green-600" />
                        ) : (
                          <Clock className="w-4 h-4 text-slate-400" />
                        )}
                      </AlertDescription>
                    </Alert>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  )
}

export default App
