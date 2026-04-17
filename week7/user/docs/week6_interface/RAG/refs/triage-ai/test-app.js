const { chromium } = require('playwright');

async function testTriageAI() {
  console.log('🧪 Testing TriageAI Application...\n');

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    // Test 1: Load homepage
    console.log('1️⃣ Loading homepage...');
    await page.goto('https://triage-ai-bay.vercel.app', { timeout: 30000 });
    await page.waitForLoadState('networkidle');

    const title = await page.title();
    console.log(`   ✅ Page loaded: "${title}"`);

    // Take screenshot
    await page.screenshot({ path: '/tmp/triage-test-1-home.png' });
    console.log('   📸 Screenshot saved: /tmp/triage-test-1-home.png\n');

    // Test 2: Check for chat interface
    console.log('2️⃣ Looking for chat interface...');

    // Wait for the app to initialize
    await page.waitForTimeout(2000);

    // Look for input field or chat elements
    const chatInput = await page.$('input, textarea, [contenteditable="true"]');
    if (chatInput) {
      console.log('   ✅ Chat input found\n');
    } else {
      console.log('   ⚠️ No chat input found - checking page content...');
      const content = await page.textContent('body');
      console.log(`   Page content preview: ${content.substring(0, 200)}...\n`);
    }

    // Take screenshot of current state
    await page.screenshot({ path: '/tmp/triage-test-2-interface.png' });
    console.log('   📸 Screenshot saved: /tmp/triage-test-2-interface.png\n');

    // Test 3: Try to interact with chat
    console.log('3️⃣ Testing chat interaction...');

    // Look for any input element
    const inputs = await page.$$('input[type="text"], textarea');
    console.log(`   Found ${inputs.length} text input(s)`);

    if (inputs.length > 0) {
      // Type a test message
      await inputs[0].fill('I have a mild headache');
      console.log('   ✅ Typed test message: "I have a mild headache"');

      await page.screenshot({ path: '/tmp/triage-test-3-typed.png' });

      // Look for send button
      const sendButton = await page.$('button[type="submit"], button:has-text("Send"), button:has-text("Submit")');
      if (sendButton) {
        await sendButton.click();
        console.log('   ✅ Clicked send button');

        // Wait for response
        await page.waitForTimeout(5000);
        await page.screenshot({ path: '/tmp/triage-test-4-response.png' });
        console.log('   📸 Screenshot saved: /tmp/triage-test-4-response.png\n');
      }
    }

    // Test 4: Check API directly
    console.log('4️⃣ Testing API endpoint...');
    const apiResponse = await page.evaluate(async () => {
      const res = await fetch('/api/conversation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      return res.json();
    });

    if (apiResponse.conversationId) {
      console.log(`   ✅ API working - Conversation ID: ${apiResponse.conversationId}`);
      console.log(`   ✅ Greeting: "${apiResponse.message.substring(0, 50)}..."\n`);
    } else {
      console.log('   ❌ API error:', apiResponse);
    }

    // Test 5: Test emergency case
    console.log('5️⃣ Testing emergency triage...');
    const emergencyResponse = await page.evaluate(async (convId) => {
      const res = await fetch('/api/conversation/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversationId: convId,
          message: 'I have severe chest pain and difficulty breathing'
        })
      });
      return res.json();
    }, apiResponse.conversationId);

    if (emergencyResponse.triageResult) {
      console.log('   ✅ Triage completed!');
      console.log(`   Urgency: ${emergencyResponse.triageResult.result?.urgency || 'N/A'}`);
      console.log(`   Red Flags: ${emergencyResponse.triageResult.result?.redFlags?.detected ? 'DETECTED' : 'None'}`);
    } else {
      console.log(`   Response: ${emergencyResponse.message?.substring(0, 100)}...`);
    }

    console.log('\n✅ All tests completed!');

  } catch (error) {
    console.error('❌ Test failed:', error.message);
    await page.screenshot({ path: '/tmp/triage-test-error.png' });
    console.log('📸 Error screenshot saved: /tmp/triage-test-error.png');
  } finally {
    await browser.close();
  }
}

testTriageAI();
