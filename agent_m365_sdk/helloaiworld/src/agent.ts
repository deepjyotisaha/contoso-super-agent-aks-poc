import { ActivityTypes } from "@microsoft/agents-activity";
import { AgentApplication, MemoryStorage, TurnContext } from "@microsoft/agents-hosting";

// AKS endpoint URL — set AKS_ENDPOINT_URL in .localConfigs (local) or App Service env vars (deployed)
const AKS_ENDPOINT_URL = process.env.AKS_ENDPOINT_URL || "http://localhost:8000/api/prompt";

const storage = new MemoryStorage();
export const agentApp = new AgentApplication({ storage });

agentApp.onConversationUpdate("membersAdded", async (context: TurnContext) => {
  await context.sendActivity(`Hi there - I'm Contoso Super Agent, fetching data from the API on Azure Kubernetes Services!`);
});

agentApp.onActivity(ActivityTypes.Message, async (context: TurnContext) => {
  const response = await fetch(AKS_ENDPOINT_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt: context.activity.text,
    }),
  });

  const data = await response.json();
  const formatted = `**Response from Contoso Super Agent AKS API**\n\n${data.response}`;
  await context.sendActivity(formatted);
});
