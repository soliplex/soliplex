# **Architectural Paradigms for Agentic Server-Driven Interfaces: A Comprehensive Analysis of State Synchronization and Schema Contracts**

## **1\. Introduction: The Evolution from Declarative to Agentic Interfaces**

The software industry stands at a critical inflection point where the role of the frontend client is fundamentally shifting. For the past decade, the dominant paradigm has been declarative UI, where the client holds the logic and state, fetching passive data from a server to populate pre-determined templates. However, the emergence of Agentic Artificial Intelligence (AI), specifically systems powered by Large Language Models (LLMs) capable of reasoning and tool use, necessitates a transition to **Agentic UI (AGUI)**. In this new architecture, the server does not merely serve data; it serves *intent*, *structure*, and *behavior*. The interface itself becomes a fluid manifestation of the AI's reasoning process, capable of restructuring itself in real-time to best serve the user's immediate context.

This shift presents a profound engineering challenge, particularly when bridging the divide between a dynamic, Python-centric backend ecosystem (leveraging FastAPI and Pydantic AI) and a strictly typed, compiled frontend ecosystem (Flutter and Dart). The "impedance mismatch" between Python's runtime flexibility and Dart's compile-time rigor creates a friction point that, if not managed through robust architectural patterns, leads to fragile applications prone to runtime failures.

The objective of this report is to provide an exhaustive architectural blueprint for building a resilient AGUI system. It explores novel methods for formalizing the JSON contract between Pydantic agents and Flutter clients, ensuring that these contracts are explicit, maintainable, and friendly to Dart's build\_runner code generation ecosystem. Furthermore, it analyzes five distinct synchronization scenarios—ranging from atomic state snapshots to complex client-side tool execution—providing a theoretical and practical framework for maintaining state consistency across the wire. By synthesizing insights from existing Server-Driven UI (SDUI) frameworks like Mirai, Stac, and Remote Flutter Widgets (RFW) with the emergent patterns of Generative UI, this document offers a definitive guide to bridging the JSON/Flutter gap in the age of Agentic AI.

## **2\. The Theoretical Foundation: The "Schema-First" Widget Registry**

The central problem in Server-Driven UI is the "Contract Problem." In a traditional REST or GraphQL API, the schema defines data entities (e.g., a User or Product). In AGUI, the schema must define the *visual components themselves* (e.g., Column, Text, Button) and their hierarchical relationships. When an AI agent generates a UI, it is effectively writing code in a domain-specific language (DSL) defined by this schema. If the agent "hallucinates" a property that the client does not support, or if the data types mismatch, the client-side renderer will fail.

To solve this, we must move beyond treating JSON as a loose transport format and elevate it to the status of a **Compilable Interface Definition**. The industry standard practice of manually parsing Map\<String, dynamic\> in Dart is insufficient for the complexity of agentic systems. Instead, a **Schema-First Widget Registry** pattern is required. This pattern inverts the typical workflow: rather than writing widget parsing logic manually, the system defines UI components as abstract data types in a shared schema language, which then generates the strict contracts for both the Python backend and the Dart frontend.

### **2.1 The Polymorphic Nature of UI Schemas**

User interfaces are inherently polymorphic. A container widget, such as a Column in Flutter, accepts a list of children. These children are not uniform; one might be a text block, the next an image, and the third a complex interactive form. In data modeling terms, this requires a robust implementation of **Discriminated Unions** (also known as Tagged Unions or Algebraic Data Types).

On the wire, this polymorphism is represented via a discriminator field, conventionally named type or $type. For example, a JSON object { "type": "button", "label": "Submit" } is distinct from { "type": "text", "content": "Hello" }. A robust AGUI architecture must enforce this discrimination at the serialization level on the server and the deserialization level on the client.

| Feature | Python (Backend) | Dart (Frontend) | JSON Representation |
| :---- | :---- | :---- | :---- |
| **Type System** | Dynamic (with Type Hints) | Static (Strongly Typed) | Untyped (Loose) |
| **Polymorphism** | typing.Union / Annotated | sealed class / Freezed | Discriminator field (type) |
| **Validation** | Pydantic (Runtime) | json\_serializable (Compile) | JSON Schema validation |
| **Null Safety** | Optional | T? | Key presence / null |

The table above highlights the mapping challenge. The goal is to ensure that a Pydantic model on the backend maps 1:1 to a Freezed class on the frontend, with the JSON acting as a verifiable intermediate representation.

### **2.2 Novel Insight: The Shared Schema Definition Pipeline**

One of the most persistent complaints regarding Flutter development is the slowness of build\_runner, the tool used for code generation. In complex SDUI applications, changing a single line of code can trigger a massive recompilation of serialization logic. To make the AGUI contract "build\_runner friendly" and maintainable, we propose a **De-coupled Schema Pipeline**.

This architectural pattern involves extracting the UI contract into a standalone, language-agnostic definition or a dedicated "Schema Package" that is compiled independently of the main application logic.

#### **2.2.1 Phase 1: The Pydantic Source of Truth**

The Pydantic AI framework relies on Pydantic models to structure the output of LLMs. Therefore, the Python models should serve as the source of truth. We define the UI component hierarchy using Annotated\[Union\[...\], Field(discriminator='type')\]. This allows Pydantic to validate the AI's output *before* it leaves the server. If the agent generates an invalid widget structure, the Pydantic validation layer catches it, preventing the "Garbage In, Garbage Out" problem that plagues many SDUI implementations.1

#### **2.2.2 Phase 2: Automated Schema Extraction**

Instead of manually writing equivalent Dart classes, which leads to drift and maintenance headaches, we utilize an automated pipeline. We can leverage Pydantic's ability to export **OpenAPI** or **JSON Schema** definitions. By utilizing libraries like datamodel-code-generator or custom scripts, we can mathematically guarantee that the schema expected by the frontend matches the schema produced by the backend.3

#### **2.2.3 Phase 3: The "Schema Package" Strategy**

To address the build\_runner performance issue, the generated Dart code should be placed in a separate Dart package (e.g., agui\_schema).

1. **Isolation:** This package contains *only* the freezed data classes and the json\_serializable logic. It contains zero Flutter widget code.  
2. **Stability:** Because the schema changes less frequently than the UI rendering logic, build\_runner only needs to run on this package when the protocol itself is updated.  
3. **Dependency:** The main Flutter application depends on agui\_schema. This separation of concerns allows developers to iterate on the renderer (the visual representation) without triggering the expensive serialization code generation loop.5

### **2.3 Implementing the Shadow Tree**

The result of this pipeline is what we term a **Shadow Tree**. In the Flutter application, this is a hierarchy of immutable Dart objects (e.g., UiColumn, UiText) that exactly mirrors the JSON structure. This tree is distinct from the Flutter **Widget Tree**.

The Shadow Tree serves as the "Model" in the MVVM pattern. It is the pure data representation of the interface. The "View" is the actual Flutter Widget tree, which is a projection of the Shadow Tree. This distinction is crucial for testing and maintenance. We can unit test the Shadow Tree's logic (e.g., "does clicking this button update the state correctly?") without needing to spin up the Flutter engine or integration tests.7

## **3\. Backend Architecture: The Agentic UI Server**

The backend of an AGUI system is not a traditional CRUD API; it is a **UI Server**. Its primary responsibility is to interpret the state of the agentic workflow and project it into a visual representation. Using **FastAPI** and **Pydantic AI**, the backend acts as the orchestrator of the user experience.

### **3.1 Pydantic Graphs as UI State Machines**

Pydantic AI agents typically operate on directed acyclic graphs (DAGs) or state machines. In an AGUI context, each node in the agent's reasoning graph can correspond to a specific UI state. For example, a "reasoning" node might emit a ThinkingWidget (a skeleton loader with streaming text), while a "result" node emits a DashboardWidget populated with data.

The response\_model feature of FastAPI is critical here. By enforcing a response\_model that creates a union of all possible UI widgets, we ensure that the API documentation (Swagger/OpenAPI) accurately reflects the polymorphic nature of the UI protocol. This documentation becomes the blueprint for the client-side code generation discussed in Section 2\.9

### **3.2 The Imperative of Streaming**

Latency is the primary enemy of Agentic UI. Users accustomed to instant mobile app interactions will not tolerate the multi-second delays often associated with LLM inference. Therefore, the architecture must support **streaming** at a fundamental level.

FastAPI's StreamingResponse allows the server to push data to the client as it is generated. In the context of AGUI, we must distinguish between three types of streaming:

1. **Token Streaming:** The standard "typewriter" effect for text content.  
2. **Structural Streaming:** Sending the UI tree in chunks (e.g., a list that populates item by item).  
3. **Partial JSON Streaming:** A more advanced technique where the raw JSON bytes are streamed and the client attempts to parse them incrementally. This allows the UI to render the "shape" of the content (e.g., a card container) before the "content" (e.g., the text inside) has fully arrived.11

## **4\. Frontend Architecture: The Flutter Client Registry**

The Flutter client in an AGUI architecture behaves less like a traditional app and more like a browser or a game engine. Its primary job is to take the Shadow Tree (the data) and render it using a library of native widgets.

### **4.1 The Registry Pattern**

The mechanism that bridges the JSON/Flutter gap is the **Widget Registry**. This is a singleton or a dependency-injected service that maps the string identifiers (discriminators) from the JSON to Flutter widget builders.

Dart

// Conceptual Registry Entry  
registry.register('info\_card', (data) \=\> InfoCardWidget(data));

To make this maintainable and explicit, we leverage Dart's strong typing. Instead of passing Map\<String, dynamic\> to the builder, we pass the strongly typed Freezed object from our Shadow Tree.

Dart

// Strongly Typed Registry  
Widget build(UiComponent component) {  
  return component.map(  
    text: (node) \=\> TextWidget(node),  
    button: (node) \=\> ButtonWidget(node),  
    column: (node) \=\> ColumnWidget(node),  
    // Exhaustiveness checking ensures we handle every case defined in the schema  
  );  
}

The use of Freezed's .map or .when methods provides **compile-time exhaustiveness checking**. If the backend team adds a new widget type Carousel to the schema package, the Flutter project will fail to compile until the Carousel case is handled in the renderer. This effectively eliminates the class of bugs where the client crashes due to unhandled widget types.13

### **4.2 Handling "Unknown" Widgets (Versioning)**

Despite our best efforts with schema sharing, version drift is inevitable. The server might deploy a new feature before the client app has been updated in the App Store. A robust AGUI client must implement a **Fallback Strategy**.

1. **Graceful Degradation:** If the registry encounters an unknown type, it should render a SizedBox.shrink() (invisible) or a generic placeholder, rather than throwing an exception.  
2. **Upgrade Prompts:** The "Unknown Widget" placeholder can be an interactive widget prompting the user to update the application to view the content.  
3. **Server-Side Fallbacks:** A sophisticated pattern involves the server sending a fallback field in the JSON. If the client doesn't recognize the primary type, it attempts to render the fallback widget (e.g., rendering a raw Text description if the InteractiveChart widget is unavailable).15

## **5\. Five Scenarios of Synchronization: Staying in Sync**

The user query requests five specific scenarios where the client and server use different features of the AGUI protocol to stay in sync. These scenarios represent a gradient of complexity, from simple full-screen refreshes to complex, bidirectional tool execution.

### **Scenario 1: The Atomic State Snapshot (Full Replacement)**

**Concept:** This is the baseline synchronization method. The server sends the complete description of the current screen state. It is analogous to a standard web page load but within a mobile context.

**Mechanism:**

1. **Trigger:** The user performs a navigation action or a "reset" interaction.  
2. **Server Action:** The Agent constructs the full widget tree for the requested view.  
3. **Protocol:** A standard HTTP GET or POST request returns the full JSON tree rooted at a Screen object.  
4. **Client Logic:** The client deserializes the entire JSON payload into a new Shadow Tree. It replaces the current state held in a Riverpod provider or Bloc.  
5. **Reconciliation:** Flutter's core engine handles the diffing. Even though we replaced the *data* tree, Flutter's *Element* tree compares the new widgets with the old ones. If a Text widget is identical in the new tree, it is not repainted.

**Insight:** While "sending everything" seems inefficient, it is the most robust method for preventing **State Drift**. In complex agentic flows where the conversation history might change non-linearly (e.g., the agent edits a previous message), attempting to calculate diffs can be error-prone. Atomic snapshots guarantee that the client sees exactly what the server intends.17

### **Scenario 2: JSON Patch Streaming (The Delta Update)**

**Concept:** For real-time interactions, such as an agent streaming a response or a live progress bar, sending the full tree repeatedly is bandwidth-prohibitive. We utilize **JSON Patch (RFC 6902\)** to transmit only the changes.

**Mechanism:**

1. **Trigger:** The agent is "thinking" or generating tokens.  
2. **Server Action:** The server maintains a hash of the previous state sent to the client. As the new state is generated, it calculates the diff.  
3. **Protocol:** The server streams a series of patch operations:  
   JSON  
   \[  
     { "op": "add", "path": "/body/children/-", "value": { "type": "text\_bubble", "text": "..." } },  
     { "op": "replace", "path": "/body/children/5/text", "value": "Analysis complete." }  
   \]

4. **Client Logic:** The client maintains a *mutable* copy of the current JSON state. Upon receiving a patch event (via SSE or WebSocket), it applies the patch using a Dart json\_patch library. It then triggers a rebuild by converting the patched JSON back into the immutable Shadow Tree.

**Insight:** This approach bridges the gap between Pydantic's immutable models and the need for high-frequency updates. While Pydantic models are immutable, the JSON representation is not. By applying the patch at the JSON layer *before* deserialization, we achieve efficient updates without breaking the immutable architecture of the Dart client.19

### **Scenario 3: Optimistic Client Actions (The Intent)**

**Concept:** To provide a "native" feel, the UI must react instantly to user input, even before the server acknowledges the action. This is crucial for simple interactions like "liking" a message or toggling a switch.

**Mechanism:**

1. **Trigger:** User taps a "Like" button.  
2. **Protocol:** The widget definition in the JSON includes an optimistic payload alongside the server action.  
   JSON  
   {  
     "type": "button",  
     "action": "toggle\_like",  
     "optimistic": { "op": "replace", "path": "/liked", "value": true }  
   }

3. **Client Logic:**  
   * The generic ActionHandler intercepts the tap.  
   * It *immediately* applies the optimistic patch to the local Shadow Tree, causing the heart icon to turn red instantly.  
   * It asynchronously sends the toggle\_like intent to the server.  
4. **Reconciliation:**  
   * **Success:** The server sends a confirmation (or a new patch that matches the local state). The client commits the change.  
   * **Failure:** The server sends a "Rollback" command or a full Snapshot. The client reverts the optimistic patch, and the heart icon turns back to grey, perhaps accompanied by an error toast.

**Insight:** This scenario requires the generic Action Handler to manage a "pending state" queue. It moves the complexity of optimistic UI from specific widget implementations to the architectural framework itself, allowing *any* server-driven widget to define optimistic behaviors.22

### **Scenario 4: Generative Partial Streaming (The Flow)**

**Concept:** This scenario addresses the "ChatGPT effect" where the UI structure itself (not just the text) is generated on the fly. The agent might decide to insert a chart, then a table, then a summary. The client should render these components as they are conceived, not wait for the entire response.

**Mechanism:**

1. **Trigger:** Complex query requiring multi-modal output.  
2. **Server Action:** The Agent begins streaming the response. Pydantic is used to serialize chunks of the object graph.  
3. **Protocol:** The server streams raw JSON bytes. Crucially, the stream might cut off in the middle of a widget definition: \`... {"type": "chart", "data":

### **Scenario 5: Client-Side Tool Calling (The Hybrid)**

**Concept:** An Agentic UI often needs to break out of the "screen" to interact with the device hardware (camera, geolocation, biometrics) or third-party SDKs. The server cannot render a "Camera View"; it can only command the client to open one.

**Mechanism:**

1. **Trigger:** The Agent determines the user needs to scan a QR code.  
2. **Server Action:** Instead of sending a Widget, the server sends a Command or ToolCall object.  
   JSON  
   {  
     "type": "command",  
     "command\_name": "scan\_qr",  
     "callback\_id": "qr\_request\_123"  
   }

3. **Client Logic:**  
   * The Registry (or a specialized CommandRegistry) identifies the type: command.  
   * It delegates execution to a **Native Bridge** (using Flutter's MethodChannel).  
   * The Flutter app opens the camera overlay, scans the code, and closes the camera.  
4. **Sync:** The client sends a "Tool Output" event back to the server, referencing the callback\_id and containing the scanned data ("https://example.com").  
5. **Loop:** The Agent receives this data as if it had called a Python function, and proceeds to generate the next UI state based on the QR code content.

**Insight:** This scenario demonstrates the true power of AGUI. The interface is not just a display; it is a remote execution environment for the Agent's tools. The JSON contract serves as the RPC (Remote Procedure Call) protocol between the AI's reasoning loop and the user's physical device.26

## **6\. Implementation Strategies: Making it Explicit and Clear**

To ensure these contracts are explicit and the architecture remains maintainable, we must adhere to specific implementation guidelines.

### **6.1 Build Runner Friendliness via Package Isolation**

The primary friction point in using freezed and json\_serializable is the build time. To mitigate this:

* **Architectural Split:** Create a separate Dart package (e.g., agui\_protocol) solely for the data models.  
* **Workflow:** Run build\_runner only within this package and only when the protocol changes. The main Flutter app consumes this package as a standard dependency.  
* **Result:** The main app's hot reload / hot restart cycle remains instant because it is not burdened by the code generation overhead of the schema.

### **6.2 The "Strict Mode" Agent**

On the backend, we must ensure the Agent does not deviate from the contract.

* **Pydantic Strict Mode:** Use model\_config \= ConfigDict(strict=True) in Pydantic models. This forbids type coercion (e.g., passing the string "123" for an integer field).  
* **Structured Output:** When interfacing with LLMs (e.g., OpenAI or Anthropic), utilize their "Function Calling" or "Structured Output" modes, passing the JSON Schema derived from the Pydantic models. This forces the LLM to generate valid JSON that conforms to our agui\_protocol.2

### **6.3 Declarative Actions**

Avoid sending executable code (like JavaScript or Dart snippets) in the JSON. This is a security risk and hard to debug. Instead, use **Declarative Actions**. The JSON should describe *what* needs to happen, not *how*.

* **Bad:** "onTap": "Navigator.pushNamed('/details')"  
* **Good:** "onTap": { "type": "navigate", "destination": "details\_screen", "args": {...} }

The Flutter client maintains an ActionRegistry that maps these declarative intents to actual code execution. This keeps the business logic on the server (deciding *where* to go) and the implementation details on the client (executing the navigation).29

## **7\. Performance and Optimization**

### **7.1 Offloading Parsing to Isolates**

Parsing large JSON structures on the main UI thread in Flutter can cause "jank" (dropped frames). The AGUI architecture should enforce parsing in background threads.

* **Compute:** Use Flutter's compute() function to run jsonDecode and Freezed.fromJson in a separate Isolate.  
* **Result:** The UI thread is free to run animations while the next screen state is being processed in the background.31

### **7.2 Lazy Loading and Pagination**

Agents can generate infinite lists. The protocol must support **LazyWidgets**.

* **Mechanism:** The server sends a LazyList widget containing a data\_url.  
* **Client:** The Flutter ListView.builder detects when the scroll position nears the bottom and triggers a request to data\_url. The server responds with the next "page" of widget definitions.  
* **Benefit:** This keeps the initial payload small and the memory footprint low.32

### **7.3 Texture Rendering vs. Native Widgets**

For extreme performance (e.g., 60fps animations driven by the server), the standard Widget tree might be too heavy. In these edge cases, we can look to architectures like **RFW (Remote Flutter Widgets)**, which uses a compact binary format instead of JSON. However, for most AGUI applications, the optimized JSON-to-Freezed pipeline described above offers the best balance of developer experience and performance.34

## **8\. Conclusion**

The transition to Agentic UI requires a fundamental rethinking of the client-server relationship. By treating the frontend as a generic rendering engine and the backend as an intelligent intent server, we unlock the potential for truly dynamic, personalized, and adaptive interfaces.

The architecture proposed in this report—anchored by the **Schema-First Widget Registry** and the **Pydantic-to-Freezed Pipeline**—provides a robust solution to the "Contract Problem." It bridges the gap between Python's flexibility and Dart's safety, ensuring that the system is stable, maintainable, and explicitly typed.

Through the implementation of the five synchronization scenarios, developers can handle the full spectrum of user interactions, from atomic screen updates to complex, multi-turn tool executions. This blueprint transforms the mobile app from a static artifact into a living, reasoning extension of the AI agent, ready to meet the user's needs in real-time.

### **Summary of Recommendations**

1. **Adopt a Schema-First approach:** Generate both Pydantic models and Dart Freezed classes from a shared definition to guarantee contract validity.  
2. **Isolate the Schema:** Place the generated code in a separate Dart package to maintain a fast development loop.  
3. **Use Discriminated Unions:** Rely on type fields to drive polymorphic deserialization on the client.  
4. **Implement Robust Syncing:** utilize Atomic Snapshots for consistency and JSON Patch for performance.  
5. **Leverage Background Parsing:** Use Flutter Isolates to keep the UI smooth during heavy state updates.  
6. **Secure the Bridge:** Use declarative actions and strict schema validation to prevent security vulnerabilities and runtime crashes.

#### **Works cited**

1. openapi-pydantic \- PyPI, accessed December 9, 2025, [https://pypi.org/project/openapi-pydantic/](https://pypi.org/project/openapi-pydantic/)  
2. FastAPI and Pydantic: A Powerful Duo \- Theodo Data & AI, accessed December 9, 2025, [https://data-ai.theodo.com/en/technical-blog/fastapi-pydantic-powerful-duo](https://data-ai.theodo.com/en/technical-blog/fastapi-pydantic-powerful-duo)  
3. datamodel-code-generator \- Pydantic Validation, accessed December 9, 2025, [https://docs.pydantic.dev/latest/integrations/datamodel\_code\_generator/](https://docs.pydantic.dev/latest/integrations/datamodel_code_generator/)  
4. How To Generate an OpenAPI Document With Pydantic V2 \- Speakeasy, accessed December 9, 2025, [https://www.speakeasy.com/openapi/frameworks/pydantic](https://www.speakeasy.com/openapi/frameworks/pydantic)  
5. openapi\_repository 2.0.1 | Flutter package \- Pub.dev, accessed December 9, 2025, [https://pub.dev/packages/openapi\_repository/versions/2.0.1](https://pub.dev/packages/openapi_repository/versions/2.0.1)  
6. carp\_serializable | Flutter package \- Pub.dev, accessed December 9, 2025, [https://pub.dev/packages/carp\_serializable](https://pub.dev/packages/carp_serializable)  
7. Stac: Server Driven UI framework for Flutter \- DEV Community, accessed December 9, 2025, [https://dev.to/smartterss/stac-server-driven-ui-framework-for-flutter-701](https://dev.to/smartterss/stac-server-driven-ui-framework-for-flutter-701)  
8. json\_dynamic\_widget | Flutter package \- Pub.dev, accessed December 9, 2025, [https://pub.dev/packages/json\_dynamic\_widget](https://pub.dev/packages/json_dynamic_widget)  
9. Data Modeling with Pydantic and FastAPI | CodeSignal Learn, accessed December 9, 2025, [https://codesignal.com/learn/courses/working-with-data-models-in-fastapi/lessons/data-modeling-with-pydantic-and-fastapi](https://codesignal.com/learn/courses/working-with-data-models-in-fastapi/lessons/data-modeling-with-pydantic-and-fastapi)  
10. Custom Response \- HTML, Stream, File, others \- FastAPI, accessed December 9, 2025, [https://fastapi.tiangolo.com/advanced/custom-response/](https://fastapi.tiangolo.com/advanced/custom-response/)  
11. JSON \- Pydantic Validation, accessed December 9, 2025, [https://docs.pydantic.dev/latest/concepts/json/](https://docs.pydantic.dev/latest/concepts/json/)  
12. Building a Real-time Streaming API with FastAPI and OpenAI: A Comprehensive Guide | by stark | Medium, accessed December 9, 2025, [https://medium.com/@shudongai/building-a-real-time-streaming-api-with-fastapi-and-openai-a-comprehensive-guide-cb65b3e686a5](https://medium.com/@shudongai/building-a-real-time-streaming-api-with-fastapi-and-openai-a-comprehensive-guide-cb65b3e686a5)  
13. freezed | Dart package \- Pub.dev, accessed December 9, 2025, [https://pub.dev/packages/freezed](https://pub.dev/packages/freezed)  
14. How to Use Freezed in Flutter \- freeCodeCamp, accessed December 9, 2025, [https://www.freecodecamp.org/news/how-to-use-freezed-in-flutter/](https://www.freecodecamp.org/news/how-to-use-freezed-in-flutter/)  
15. Server‑Driven UI in Flutter Using JSON Configuration \- Vibe Studio, accessed December 9, 2025, [https://vibe-studio.ai/insights/server-driven-ui-in-flutter-using-json-configuration](https://vibe-studio.ai/insights/server-driven-ui-in-flutter-using-json-configuration)  
16. How to Build Resilient API-Driven UIs in Flutter \- Digia Studio, accessed December 9, 2025, [https://www.digia.tech/post/how-to-build-resilient-api-driven-uis-in-flutter](https://www.digia.tech/post/how-to-build-resilient-api-driven-uis-in-flutter)  
17. Server Driven UI Flutter: The Complete Guide for 2025 \- VideoSDK, accessed December 9, 2025, [https://www.videosdk.live/developer-hub/social/server-driven-ui-flutter](https://www.videosdk.live/developer-hub/social/server-driven-ui-flutter)  
18. Create Dynamic Flutter App UI with Server-Driven Design \- Flutternest, accessed December 9, 2025, [https://flutternest.com/blog/flutter-server-driven-ui](https://flutternest.com/blog/flutter-server-driven-ui)  
19. JSON Patch | jsonpatch.com, accessed December 9, 2025, [https://jsonpatch.com/](https://jsonpatch.com/)  
20. json\_patch \- Dart API docs \- Pub.dev, accessed December 9, 2025, [https://pub.dev/documentation/json\_patch/latest/](https://pub.dev/documentation/json_patch/latest/)  
21. JSON-delta: a diff/patch pair for JSON-serialized data structures — JSON-delta 2.0 documentation, accessed December 9, 2025, [https://json-delta.readthedocs.io/](https://json-delta.readthedocs.io/)  
22. Optimistic State in Flutter Explained | by Gerald Nuraj \- Medium, accessed December 9, 2025, [https://medium.com/@geraldnuraj/optimistic-state-in-flutter-explained-3dec68ae6252](https://medium.com/@geraldnuraj/optimistic-state-in-flutter-explained-3dec68ae6252)  
23. Building an optimistic update hook for Flutter apps \- Matthew Trent, accessed December 9, 2025, [https://matthewtrent.me/articles/use-optimistic](https://matthewtrent.me/articles/use-optimistic)  
24. Optimistic state \- Flutter documentation, accessed December 9, 2025, [https://docs.flutter.dev/app-architecture/design-patterns/optimistic-state](https://docs.flutter.dev/app-architecture/design-patterns/optimistic-state)  
25. invokeMethod method \- OptionalMethodChannel class \- services library \- Dart API \- Flutter, accessed December 9, 2025, [https://api.flutter.dev/flutter/services/OptionalMethodChannel/invokeMethod.html](https://api.flutter.dev/flutter/services/OptionalMethodChannel/invokeMethod.html)  
26. AG-UI Overview \- Agent User Interaction Protocol, accessed December 9, 2025, [https://docs.ag-ui.com/introduction](https://docs.ag-ui.com/introduction)  
27. ag-ui-protocol/ag-ui: AG-UI: the Agent-User Interaction ... \- GitHub, accessed December 9, 2025, [https://github.com/ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui)  
28. Building Custom Widgets & Actions in Stac | by Divyanshu Bhargava \- Medium, accessed December 9, 2025, [https://medium.com/stac/building-custom-widgets-actions-in-stac-da2e0dae1dff](https://medium.com/stac/building-custom-widgets-actions-in-stac-da2e0dae1dff)  
29. Stac | Update Flutter Apps in Seconds with Server-Driven UI, accessed December 9, 2025, [https://stac.dev/](https://stac.dev/)  
30. Parse JSON in the background \- Flutter documentation, accessed December 9, 2025, [https://docs.flutter.dev/cookbook/networking/background-parsing](https://docs.flutter.dev/cookbook/networking/background-parsing)  
31. Lazy Loading in Flutter \- Medium, accessed December 9, 2025, [https://medium.com/@rk0936626/lazy-loading-in-flutter-2df923d56fd3](https://medium.com/@rk0936626/lazy-loading-in-flutter-2df923d56fd3)  
32. Mastering Data Handling in Flutter: Lazy Loading vs Pagination | by Harsh Kumar Khatri, accessed December 9, 2025, [https://mailharshkhatri.medium.com/mastering-data-handling-in-flutter-lazy-loading-vs-pagination-6b14888d3c85](https://mailharshkhatri.medium.com/mastering-data-handling-in-flutter-lazy-loading-vs-pagination-6b14888d3c85)  
33. Server-Driven UI with Flutter \- Aloïs Deniel \- async, accessed December 9, 2025, [https://async.techconnection.io/talks/flutter-connection/2024/alois-deniel-server-driven-ui-with-flutter/](https://async.techconnection.io/talks/flutter-connection/2024/alois-deniel-server-driven-ui-with-flutter/)  
34. rfw package \- Remote Flutter Widgets \- Pub.dev, accessed December 9, 2025, [https://pub.dev/documentation/rfw/latest/](https://pub.dev/documentation/rfw/latest/)