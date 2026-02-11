import { NodeStatus, OutputNodeData, useNodeContext } from '@/contexts/node-context';
import { Agent } from '@/data/agents';
import { LanguageModel } from '@/data/models';
import { extractBaseAgentKey } from '@/data/node-mappings';
import { flowConnectionManager } from '@/hooks/use-flow-connection';
import {
  HedgeFundRequest,
  DexterChatRequest,
  DexterChatResponse,
} from '@/services/types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const api = {
  /**
   * Gets the list of available agents from the backend
   * @returns Promise that resolves to the list of agents
   */
  getAgents: async (): Promise<Agent[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/hedge-fund/agents`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data.agents;
    } catch (error) {
      console.error('Failed to fetch agents:', error);
      throw error;
    }
  },

  /**
   * Gets the list of available models from the backend
   * @returns Promise that resolves to the list of models
   */
  getLanguageModels: async (): Promise<LanguageModel[]> => {
    try {
      const response = await fetch(`${API_BASE_URL}/language-models/`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      return data.models;
    } catch (error) {
      console.error('Failed to fetch models:', error);
      throw error;
    }
  },

  /**
   * Saves JSON data to a file in the project's /outputs directory
   * @param filename The name of the file to save
   * @param data The JSON data to save
   * @returns Promise that resolves when the file is saved
   */
  saveJsonFile: async (filename: string, data: any): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/storage/save-json`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename,
          data
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log(result.message);
    } catch (error) {
      console.error('Failed to save JSON file:', error);
      throw error;
    }
  },

  /**
   * Sends a prompt to Dexter for terminal-style interaction.
   */
  dexterChat: async (payload: DexterChatRequest): Promise<DexterChatResponse> => {
    const response = await fetch(`${API_BASE_URL}/hedge-fund/dexter`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  },

  /**
   * Runs a hedge fund simulation using polling (App Runner compatible).
   * Starts a background job, then polls for progress every 2.5s.
   * @returns A function to abort/cancel the job
   */
  runHedgeFund: (
    params: HedgeFundRequest,
    nodeContext: ReturnType<typeof useNodeContext>,
    flowId: string | null = null
  ): (() => void) => {
    // Convert tickers string to array if needed
    if (typeof params.tickers === 'string') {
      params.tickers = (params.tickers as unknown as string).split(',').map(t => t.trim());
    }

    const getAgentIds = () => params.graph_nodes.map(node => node.id);

    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;
    let jobId: string | null = null;

    const processEvent = (event: { type: string; data: any }) => {
      switch (event.type) {
        case 'start':
          nodeContext.resetAllNodes(flowId);
          break;
        case 'progress':
          if (event.data.agent) {
            let nodeStatus: NodeStatus = 'IN_PROGRESS';
            if (event.data.status === 'Done') {
              nodeStatus = 'COMPLETE';
            }
            const baseAgentKey = event.data.agent.replace('_agent', '');
            const uniqueNodeId = getAgentIds().find(id =>
              extractBaseAgentKey(id) === baseAgentKey
            ) || baseAgentKey;

            nodeContext.updateAgentNode(flowId, uniqueNodeId, {
              status: nodeStatus,
              ticker: event.data.ticker,
              message: event.data.status,
              analysis: event.data.analysis,
              timestamp: event.data.timestamp,
            });
          }
          break;
        case 'complete':
          if (event.data.data) {
            nodeContext.setOutputNodeData(flowId, event.data.data as OutputNodeData);
          }
          nodeContext.updateAgentNodes(flowId, getAgentIds(), 'COMPLETE');
          nodeContext.updateAgentNode(flowId, 'output', {
            status: 'COMPLETE',
            message: 'Analysis complete',
          });
          if (flowId) {
            flowConnectionManager.setConnection(flowId, {
              state: 'completed',
              abortController: null,
            });
            setTimeout(() => {
              const cur = flowConnectionManager.getConnection(flowId);
              if (cur.state === 'completed') {
                flowConnectionManager.setConnection(flowId, { state: 'idle' });
              }
            }, 30000);
          }
          break;
        case 'error':
          nodeContext.updateAgentNodes(flowId, getAgentIds(), 'ERROR');
          if (flowId) {
            flowConnectionManager.setConnection(flowId, {
              state: 'error',
              error: event.data.message || 'Unknown error occurred',
              abortController: null,
            });
          }
          break;
      }
    };

    // Start the job, then poll
    (async () => {
      try {
        // 1. Start the job
        const startRes = await fetch(`${API_BASE_URL}/hedge-fund/jobs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(params),
        });
        if (!startRes.ok) {
          throw new Error(`Failed to start job: ${startRes.status}`);
        }
        const { job_id } = await startRes.json();
        jobId = job_id;
        console.log('Job started:', jobId);

        if (cancelled) {
          // User cancelled before we even got the job ID
          fetch(`${API_BASE_URL}/hedge-fund/jobs/${jobId}/cancel`, { method: 'POST' }).catch(() => {});
          return;
        }

        // 2. Poll loop
        let cursor = -1;
        const poll = async () => {
          if (cancelled) return;
          try {
            const res = await fetch(
              `${API_BASE_URL}/hedge-fund/jobs/${jobId}?after=${cursor}`
            );
            if (!res.ok) {
              throw new Error(`Poll failed: ${res.status}`);
            }
            const data = await res.json();

            // Process new events
            for (const evt of data.events) {
              processEvent(evt);
              if (evt.index > cursor) cursor = evt.index;
            }

            // Check terminal states
            const terminal = ['complete', 'error', 'cancelled'];
            if (terminal.includes(data.status)) {
              // If complete with result but no complete event yet, handle it
              if (data.status === 'complete' && data.result) {
                // The complete event should have already been processed above,
                // but ensure output data is set
                const hasCompleteEvent = data.events.some(
                  (e: any) => e.type === 'complete'
                );
                if (!hasCompleteEvent) {
                  processEvent({ type: 'complete', data: { data: data.result } });
                }
              }
              if (data.status === 'error' && data.error) {
                const hasErrorEvent = data.events.some(
                  (e: any) => e.type === 'error'
                );
                if (!hasErrorEvent) {
                  processEvent({ type: 'error', data: { message: data.error } });
                }
              }
              console.log('Job finished with status:', data.status);
              return; // Stop polling
            }

            // Schedule next poll
            if (!cancelled) {
              pollTimer = setTimeout(poll, 2500);
            }
          } catch (err: any) {
            if (!cancelled) {
              console.error('Polling error:', err);
              nodeContext.updateAgentNodes(flowId, getAgentIds(), 'ERROR');
              if (flowId) {
                flowConnectionManager.setConnection(flowId, {
                  state: 'error',
                  error: err.message || 'Polling error',
                  abortController: null,
                });
              }
            }
          }
        };

        poll();
      } catch (error: any) {
        if (!cancelled) {
          console.error('Job start error:', error);
          nodeContext.updateAgentNodes(flowId, getAgentIds(), 'ERROR');
          if (flowId) {
            flowConnectionManager.setConnection(flowId, {
              state: 'error',
              error: error.message || 'Connection failed',
              abortController: null,
            });
          }
        }
      }
    })();

    // Return abort/cancel function
    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
      if (jobId) {
        fetch(`${API_BASE_URL}/hedge-fund/jobs/${jobId}/cancel`, {
          method: 'POST',
        }).catch(() => {});
      }
      if (flowId) {
        flowConnectionManager.setConnection(flowId, {
          state: 'idle',
          abortController: null,
        });
      }
    };
  },
}; 