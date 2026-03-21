import { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
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
  ArrowRight,
  Loader2
} from 'lucide-react';

import { useRuns, useRunDetail } from '@/hooks';
import { RunProgress, RiskBadge, SqlUnitDetail, ProposalCard } from '@/components';
import { isMockMode, MOCK_RUN_ID } from '@/lib/mockHelper';
import { deriveRiskLevel } from '@/types/v9';

// Helper to get current run ID
function getCurrentRunId(): string | null {
  // In mock mode, use mock run ID
  if (isMockMode) {
    return MOCK_RUN_ID;
  }
  // In real mode, would use selected run from runs list
  return null; // Return null to use first run or show empty state
}

function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(getCurrentRunId());
  
  // Fetch run list
  const { runs, loading: runsLoading, error: runsError } = useRuns();
  
  // If no run selected but runs exist, select first one
  const activeRunId = selectedRunId ?? (runs.length > 0 ? runs[0].id : null);
  
  // Fetch run details
  const { run, sqlUnits, proposals, loading: detailLoading, error: detailError, refresh } = useRunDetail(activeRunId);

  // Stats derived from run data
  const stats = {
    totalRuns: runs.length,
    sqlAnalyzed: run?.sqlCount ?? 0,
    issuesFound: sqlUnits.filter(u => u.riskLevel === 'HIGH' || u.riskLevel === 'MEDIUM').length,
    optimized: proposals.filter(p => p.validated).length
  };

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
            <Button variant="outline" size="sm" onClick={() => refresh()}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Refresh
            </Button>
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
        {isMockMode && (
          <Alert className="mb-4 border-blue-500 bg-blue-50">
            <AlertTitle className="text-blue-600">Mock Mode</AlertTitle>
            <AlertDescription className="text-blue-600">
              Running with mock data. Switch to real mode for actual V9 data.
            </AlertDescription>
          </Alert>
        )}

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
                      {detailLoading ? (
                        <Skeleton className="h-8 w-16 mt-1" />
                      ) : (
                        <p className="text-2xl font-bold">{stats.totalRuns}</p>
                      )}
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
                      {detailLoading ? (
                        <Skeleton className="h-8 w-16 mt-1" />
                      ) : (
                        <p className="text-2xl font-bold">{stats.sqlAnalyzed}</p>
                      )}
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
                      {detailLoading ? (
                        <Skeleton className="h-8 w-16 mt-1" />
                      ) : (
                        <p className="text-2xl font-bold">{stats.issuesFound}</p>
                      )}
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
                      {detailLoading ? (
                        <Skeleton className="h-8 w-16 mt-1" />
                      ) : (
                        <p className="text-2xl font-bold">
                          {stats.sqlAnalyzed > 0 ? Math.round((stats.optimized / stats.sqlAnalyzed) * 100) : 0}%
                        </p>
                      )}
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
                <CardDescription>
                  {run?.id ?? 'No run selected'}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {detailLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-4 w-full" />
                    <Skeleton className="h-4 w-3/4" />
                  </div>
                ) : run ? (
                  <>
                    <div className="flex items-center justify-between text-sm">
                      <span>
                        Stage: <Badge variant="outline">{run.currentStage ?? 'none'}</Badge>
                      </span>
                      <span>{run.progress}%</span>
                    </div>
                    <RunProgress 
                      completedStages={run.completedStages} 
                      currentStage={run.currentStage} 
                    />
                    <Progress value={run.progress} className="h-2" />
                    <div className="flex gap-4 text-sm text-slate-500">
                      <span>SQLs: {run.sqlCount}</span>
                      <span>Issues: {run.issueCount}</span>
                      <span>{run.startedAt}</span>
                    </div>
                  </>
                ) : (
                  <p className="text-slate-500">No run data available</p>
                )}
              </CardContent>
              <CardFooter className="gap-2">
                <Button size="sm" disabled>
                  <Pause className="w-4 h-4 mr-1" />
                  Pause
                </Button>
                <Button size="sm" variant="outline" disabled>
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
                {runsLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-8 w-full" />
                  </div>
                ) : runs.length > 0 ? (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Run ID</TableHead>
                        <TableHead>Stage</TableHead>
                        <TableHead>Progress</TableHead>
                        <TableHead>SQLs</TableHead>
                        <TableHead>Issues</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead></TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {runs.map((r) => (
                        <TableRow 
                          key={r.id} 
                          className="cursor-pointer hover:bg-slate-50"
                          onClick={() => setSelectedRunId(r.id)}
                        >
                          <TableCell className="font-mono text-sm">{r.id}</TableCell>
                          <TableCell>
                            <Badge variant={r.status === 'completed' ? 'default' : 'secondary'}>
                              {r.currentStage ?? 'none'}
                            </Badge>
                          </TableCell>
                          <TableCell>{r.progress}%</TableCell>
                          <TableCell>{r.sqlCount}</TableCell>
                          <TableCell>
                            <span className={r.issueCount > 3 ? 'text-amber-600' : ''}>
                              {r.issueCount}
                            </span>
                          </TableCell>
                          <TableCell className="text-slate-500">{r.startedAt}</TableCell>
                          <TableCell>
                            <Button size="sm" variant="ghost">
                              <ArrowRight className="w-4 h-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : (
                  <p className="text-slate-500">No runs found</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="runs" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>SQL Units</CardTitle>
                <CardDescription>
                  {sqlUnits.length} SQL statements discovered in this run
                </CardDescription>
              </CardHeader>
              <CardContent>
                {detailLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full" />
                  </div>
                ) : sqlUnits.length > 0 ? (
                  <div className="space-y-2">
                    {sqlUnits.map((sql) => (
                      <SqlUnitDetail key={sql.sqlKey} unit={sql} />
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500">No SQL units found</p>
                )}
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
                {detailLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-20 w-full" />
                    <Skeleton className="h-20 w-full" />
                  </div>
                ) : proposals.length > 0 ? (
                  <div className="space-y-4">
                    {proposals.map((prop) => (
                      <ProposalCard key={prop.sqlKey} proposal={prop} />
                    ))}
                  </div>
                ) : (
                  <p className="text-slate-500">No proposals available</p>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

export default App;
