# Pipeline  Notes
## overall workflow
- agents will read documents from one or more backing stores and pass to the parser
- parser will use docling to extract necessary info to pass to embedding model
    - parser will extract metadata, but agent may provide/override
    - parser will decide routing based upon metadata TBD
- embeddings will be stored in zero or more lancedb stores 

## knowns
- documents will come from various sources but will generally be pdf
- documents will have text and images that will need to be converted to text for rag to index
- not all images will have meaningful info and can be excluded
- documents are not well structured and can contain low entropy/un-parseable sectiokns
- documents will reference other documents so hyperlinks may need to be created
- each document should be loaded in its own process space for resilience /scaling
- errors should be recoverable for a set of documents or an individual document

## questions

### agents:
- assuming agents will use https for transport but might use a persistent queue

### parser:

- will we have to worry about scanned docs that might need heavy preprocessing to load?
- if a chunk of a document fails, should the good parts still be indexed or discard whole document?
- does the parser need to maintain a copy of a document(parsed or not) or are re-pulls practical?
- document might need to be stored until parsing/storage is complete to allow for retries
- how to copy lancedb entries for a given doc to various targets as that's not exactly replication?
- not entirely sure a DAG is required as this is more of a unidirectional process unless lancedbs are going to be chained or something. I don't think there are any scatter/gather type dependencies

### recovery:
- looks like lancedb has replication/etc? but routing/reconciliation might not be included
- what type of backup/checkpointing measures are in place?
- what's the expected time to recovery for a replication/backing store failure?

### metadata:
- will there be metadata supplied from the agent that's not in the document?
- how structured will the metadata be?  (e.g will it be known in advance?)
- how configurable/dynamic do the routing rules need to be? (e.g. will end user need to create/modify rules as rooms get created?)
### refresh
- will agents be wholly or partly responsible for change detection or just push everything?
    - i had considered using 304 not-modified status to allow central repo to maintain doc versions
- do versions need to be tracked?
    - diffs?
- will the parser need to maintain a dead-letter queue of failed docs?
