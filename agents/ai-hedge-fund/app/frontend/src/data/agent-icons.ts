import {
  Bot,
  type LucideIcon,
} from 'lucide-react';

/**
 * Maps agent keys to custom kawaii animal icon images.
 */
const AGENT_IMAGE_MAP: Record<string, string> = {
  // Famous investors
  warren_buffett: '/icons/agents/elephant.png',
  charlie_munger: '/icons/agents/hedgehog.png',
  ben_graham: '/icons/agents/turtle.png',
  michael_burry: '/icons/agents/bat.png',
  peter_lynch: '/icons/agents/cat.png',
  phil_fisher: '/icons/agents/fox.png',
  cathie_wood: '/icons/agents/dinosaur.png',
  aswath_damodaran: '/icons/agents/sheep.png',
  bill_ackman: '/icons/agents/panda.png',
  mohnish_pabrai: '/icons/agents/chick.png',
  rakesh_jhunjhunwala: '/icons/agents/bee.png',
  stanley_druckenmiller: '/icons/agents/jellyfish.png',

  // Systematic analysts
  technical_analyst: '/icons/agents/octopus.png',
  fundamentals_analyst: '/icons/agents/snail.png',
  growth_analyst: '/icons/agents/axolotl.png',
  news_sentiment_analyst: '/icons/agents/bird.png',
  sentiment_analyst: '/icons/agents/lamb.png',
  valuation_analyst: '/icons/agents/snail2.png',

  // Special agents
  dexter: '/icons/agents/rooster.png',
  devils_advocate: '/icons/agents/bull.png',
  portfolio_manager: '/icons/agents/pig.png',
};

/**
 * Strip suffixes to get the base agent key.
 */
function stripAgentKey(agentKey: string): string {
  return agentKey
    .replace(/_agent$/, '')
    .replace(/_[a-z0-9]{5,}$/, '');
}

/**
 * Get the custom image URL for an agent, or null if none exists.
 */
export function getAgentImageUrl(agentKey: string): string | null {
  if (agentKey in AGENT_IMAGE_MAP) return AGENT_IMAGE_MAP[agentKey];
  const stripped = stripAgentKey(agentKey);
  if (stripped in AGENT_IMAGE_MAP) return AGENT_IMAGE_MAP[stripped];
  return null;
}

/**
 * Get the lucide fallback icon for an agent (used when no custom image exists).
 */
export function getAgentIcon(_agentKey: string): LucideIcon {
  return Bot;
}
