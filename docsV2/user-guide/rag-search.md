# Document Search

RAG-enabled rooms can search your documents and provide answers with citations.

## How It Works

1. You ask a question
2. AI searches relevant documents using the `search_documents` tool
3. AI generates an answer using the sources
4. Citations appear below the response

## Asking Questions

### Good Questions

- "What does the policy say about remote work?"
- "Summarize the key findings from the report"
- "Compare the approaches described in documents A and B"

### Tips

- Be specific about what you're looking for
- Reference document names if known
- Ask for summaries of complex topics

## Understanding Results

### Responses

When the AI uses document search, you'll see:
- The answer to your question
- A collapsible "Citations" section below the message

### Citations Section

Click the citations header to expand. Each citation shows:

- **Document title** - Name of the source document
- **Page numbers** - For PDFs, shows which pages (clickable to view)
- **Expand arrow** - Click to see more details

### Viewing Citation Details

Click on a citation row to expand and see:
- **Headings** - Section hierarchy from the document
- **Content excerpt** - The relevant text chunk
- **Document URI** - Path to the source file

### Viewing Document Pages (PDF only)

For PDF documents, click the page badge to:
- See thumbnail images of the cited pages
- Click a thumbnail for full-size interactive view
- Zoom and pan on the document page

## Search Limitations

### What Works Well

- Factual questions about document content
- Summaries and comparisons
- Finding specific information
- Understanding complex topics

### What May Not Work

- Questions about content not in documents
- Very recent information not yet ingested
- Highly specific technical queries outside document scope

## Tips for Better Results

1. **Be specific** - "What is the Q3 revenue?" vs "Tell me about revenue"
2. **Use document terms** - Match language used in your documents
3. **Ask follow-ups** - Narrow down with additional questions
4. **Check citations** - Expand to verify the AI used relevant sources
5. **Try rephrasing** - Different wording may find different results

## Troubleshooting

### No Results Found

- Check if the room has RAG enabled (configured with `search_documents` tool)
- Try different keywords
- Verify documents have been ingested into the RAG database

### Irrelevant Results

- Be more specific in your question
- Try different phrasing
- Ask about specific document sections

### No Citations Shown

- The room may not have RAG configured
- The AI may have answered from general knowledge
- Ask "What documents mention X?" to trigger document search
