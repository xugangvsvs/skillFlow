import { CopilotClient, approveAll } from "@github/copilot-sdk";

async function main() {
  const client = new CopilotClient();

  // 创建 session 时加入权限回调
  const session = await client.createSession({
    model: "gpt-4.1",
    onPermissionRequest: approveAll, // 🔑 这里必须加
  });

  const response = await session.sendAndWait({
    prompt: "What is 2 + 2?",
  });

  console.log(response?.data.content);

  await client.stop();
}

main();
