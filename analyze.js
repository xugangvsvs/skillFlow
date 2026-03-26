import { CopilotClient, approveAll } from "@github/copilot-sdk"; // 1. 增加导入 approveAll

async function test() {
    console.log("🚀 Starting Copilot SDK test...");
    
    const client = new CopilotClient();

    try {
        console.log("建立会话中 (Creating session)...");
        
        // 2. 在这里增加 onPermissionRequest 配置
        const session = await client.createSession({
            model: "gpt-4.1",
            onPermissionRequest: approveAll 
        });

        console.log("发送请求中 (Sending prompt)...");
        const response = await session.sendAndWait({ 
            prompt: "Hello Copilot! If you can hear me, respond with 'Nokia IMS Expert Ready'." 
        });

        if (response && response.data) {
            console.log("\n✅ Copilot Response:");
            console.log(response.data.content);
        }

    } catch (error) {
        console.error("\n❌ SDK Error:");
        console.error(error.message);
    } finally {
        await client.stop();
        process.exit(0);
    }
}

test();
