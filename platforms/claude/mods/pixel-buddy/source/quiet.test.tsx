import { expect, test } from 'claude-code/testing'
import { emptyWork, quietTask, reconcile, resumeWork, started } from './hooks/background'

const task = (id: string, type = 'shell') => ({ id, type, status: 'running', description: 'fixture' })

test('监视类与内部维护类任务按类型标签或宿主任务 ID 规则忽略，其他类型照常计入', () => {
  for (const type of ['monitor', 'monitor_ws', 'monitor_mcp', 'dream', 'auto-mode scan', 'memory import']) expect(quietTask({ id: 'plain-id', type })).toBe(true)
  for (const id of ['shbjycjln', 'mabcdefgh', 'd12345678', 'eabcdefgh', 'n00000000']) expect(quietTask({ id, type: 'whatever' })).toBe(true)
  for (const [id, type] of [['bvjl1nxrg', 'shell'], ['a8fac3ba88d0c8d6f', 'subagent'], ['wabcdefgh', 'workflow'], ['kabcdefgh', 'MCP task'],
    ['tabcdefgh', 'teammate'], ['rabcdefgh', 'cloud session'], ['plain-id', undefined], ['shbjycjln9', 'shell']]) expect(quietTask({ id, type })).toBe(false)
  const work = reconcile(emptyWork(1), [task('bvjl1nxrg'), { ...task('x'), id: 'shbjycjln', type: 'monitor' }, { ...task('plain'), type: 'dream' },
    { id: 'no-type', status: 'running' }], 5)
  expect(Object.keys(work.active).sort()).toEqual(['task:bvjl1nxrg', 'task:no-type'])
  expect(work.known).toBe(true)
  expect(work.listed).toEqual({ bvjl1nxrg: 'shell', shbjycjln: 'monitor', plain: 'dream', 'no-type': '?' })
})

test('快照里记下的类型限制条数并替换异常字符；没有 type 字段的旧快照照常处理', () => {
  const many = Array.from({ length: 40 }, (_, index) => ({ ...task(`shell-${index}`), type: 'sh\nell<>' }))
  const work = reconcile(emptyWork(1), many, 5)
  expect(Object.keys(work.listed ?? {}).length).toBe(30)
  expect(work.listed?.['shell-0']).toBe('sh?ell??')
  expect(Object.keys(work.active).length).toBe(40)
})

test('同会话重载不把旧版记进来的监视类任务带过去，真实任务照常接续', () => {
  const before = started(started(emptyWork(1), 'bvjl1nxrg', 2), 'shbjycjln', 3)
  expect(Object.keys(resumeWork(before, 9).active)).toEqual(['task:bvjl1nxrg'])
})
