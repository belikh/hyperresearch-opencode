---
title: Extract, transform, load - Wikipedia
id: extract-transform-load-wikipedia
created: '2026-08-24T06:48:53.834635Z'
source: https://en.wikipedia.org/wiki/Extract,_transform,_load
source_domain: en.wikipedia.org
fetched_at: '2026-08-24T06:48:53.831549Z'
fetch_provider: parallel
status: draft
type: note
tier: institutional
content_type: article
deprecated: false
---

|[icon](https://en.wikipedia.org/wiki/File:Question_book-new.svg) |This article **needs [more citations](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability")** . Please help [improve this article](https://en.wikipedia.org/wiki/Special:EditPage/Extract,_transform,_load "Special:EditPage/Extract, transform, load") by [adding citations to reliable sources](https://en.wikipedia.org/wiki/Help:Referencing_for_beginners "Help:Referencing for beginners") . Unsourced material may be challenged and [removed](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") .  
_Find sources:_ ["Extract, transform, load"](https://www.google.com/search?as_eq=wikipedia&q=%22Extract%2C+transform%2C+load%22) – [news](https://www.google.com/search?tbm=nws&q=%22Extract%2C+transform%2C+load%22+-wikipedia&tbs=ar:1) **·** [newspapers](https://www.google.com/search?&q=%22Extract%2C+transform%2C+load%22&tbs=bkt:s&tbm=bks) **·** [books](https://www.google.com/search?tbs=bks:1&q=%22Extract%2C+transform%2C+load%22+-wikipedia) **·** [scholar](https://scholar.google.com/scholar?q=%22Extract%2C+transform%2C+load%22) **·** [JSTOR](https://www.jstor.org/action/doBasicSearch?Query=%22Extract%2C+transform%2C+load%22&acc=on&wc=on) _( September 2024 )_ _( [Learn how and when to remove this message](https://en.wikipedia.org/wiki/Help:Maintenance_template_removal "Help:Maintenance template removal") )_ |
| --- | --- |

[Conventional ETL architecture](https://en.wikipedia.org/wiki/File:Extract,_Transform,_Load_Data_Flow_Diagram.svg) Conventional ETL architecture

|[Data transformation](https://en.wikipedia.org/wiki/Data_transformation_\(computing\) "Data transformation (computing)") |
| --- |
|Concepts |
|* [Metadata](https://en.wikipedia.org/wiki/Metadata "Metadata")
* [Data element](https://en.wikipedia.org/wiki/Data_element "Data element")
* [Data mapping](https://en.wikipedia.org/wiki/Data_mapping "Data mapping")
* [Data migration](https://en.wikipedia.org/wiki/Data_migration "Data migration")
* [Data transformation](https://en.wikipedia.org/wiki/Data_transformation_\(computing\) "Data transformation (computing)")
* [Model transformation](https://en.wikipedia.org/wiki/Model_transformation "Model transformation")
* [Macro](https://en.wikipedia.org/wiki/Macro_\(computer_science\) "Macro (computer science)")
* [Preprocessor](https://en.wikipedia.org/wiki/Preprocessor "Preprocessor") |
|[Transformation languages](https://en.wikipedia.org/wiki/Transformation_language "Transformation language") |
|* [ATL](https://en.wikipedia.org/wiki/ATLAS_Transformation_Language "ATLAS Transformation Language")
* [AWK](https://en.wikipedia.org/wiki/AWK "AWK")
* [MOFM2T](https://en.wikipedia.org/wiki/MOFM2T "MOFM2T")
* [QVT](https://en.wikipedia.org/wiki/QVT "QVT")
* [XML languages](https://en.wikipedia.org/wiki/XML_transformation_language "XML transformation language") |
|Techniques and transforms |
|* [Identity transform](https://en.wikipedia.org/wiki/Identity_transform "Identity transform")
* [Data refinement](https://en.wikipedia.org/wiki/Data_refinement "Data refinement") |
|Applications |
|* [Data conversion](https://en.wikipedia.org/wiki/Data_conversion "Data conversion")
* [Data migration](https://en.wikipedia.org/wiki/Data_migration "Data migration")
* [Data integration](https://en.wikipedia.org/wiki/Data_integration "Data integration")
* [Extract, transform, load](https://en.wikipedia.org/wiki/Extract,_transform,_load) (ETL)
* [Web template system](https://en.wikipedia.org/wiki/Web_template_system "Web template system") |
|Related |
|* [Data wrangling](https://en.wikipedia.org/wiki/Data_wrangling "Data wrangling")
* [Transformation languages](https://en.wikipedia.org/wiki/Transformation_language "Transformation language") |
|* [v](https://en.wikipedia.org/wiki/Template:Data_transformation "Template:Data transformation")
* [t](https://en.wikipedia.org/wiki/Template_talk:Data_transformation "Template talk:Data transformation")
* [e](https://en.wikipedia.org/wiki/Special:EditPage/Template:Data_transformation "Special:EditPage/Template:Data transformation") |

**Extract, transform, load** ( **ETL** ) is a three-phase [computing](https://en.wikipedia.org/wiki/Computing "Computing") process where data are [_extracted_](https://en.wikipedia.org/wiki/Data_extraction "Data extraction") from an input source, [_transformed_](https://en.wikipedia.org/wiki/Data_transformation "Data transformation") (including [cleaning](https://en.wikipedia.org/wiki/Data_cleaning "Data cleaning") ), and [_loaded_](https://en.wikipedia.org/wiki/Data_loading "Data loading") into an output data container. The data can be collected from one or more sources and it can also be output to one or more destinations. ETL processing is typically executed using [software applications](https://en.wikipedia.org/wiki/Software_application "Software application") but it can also be done manually by system operators. ETL software typically automates the entire process and can be run manually or on recurring schedules either as single jobs or aggregated into a batch of jobs.

A properly designed ETL system extracts data from source systems and enforces data type and data validity standards and ensures it conforms structurally to the requirements of the output. Some ETL systems can also deliver data in a presentation-ready format so that application developers can build applications and end users can make decisions. [[ 1 ]]()

The ETL process is often used in [data warehousing](https://en.wikipedia.org/wiki/Data_warehouse "Data warehouse") . [[ 2 ]]() ETL systems commonly integrate data from multiple applications (systems), typically developed and supported by different [vendors](https://en.wikipedia.org/wiki/Vendor "Vendor") or hosted on separate computer hardware. The separate systems containing the original data are frequently managed and operated by different [stakeholders](https://en.wikipedia.org/wiki/Stakeholder_\(corporate\) "Stakeholder (corporate)") . For example, a cost accounting system may combine data from payroll, sales, and purchasing.

Data extraction involves extracting data from homogeneous or heterogeneous sources; data transformation processes data by data cleaning and transforming it into a proper storage format/structure for the purposes of querying and analysis; finally, data loading describes the insertion of data into the final target database such as an [operational data store](https://en.wikipedia.org/wiki/Operational_data_store "Operational data store") , a [data mart](https://en.wikipedia.org/wiki/Data_mart "Data mart") , [data lake](https://en.wikipedia.org/wiki/Data_lake "Data lake") or a data warehouse. [[ 3 ]]() [[ 4 ]]()

ETL and its variant ELT (extract, load, transform), are increasingly used in cloud-based data warehousing. Applications involve not only batch processing, but also real-time streaming.

## Phases

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=1 "Edit section: Phases") ]

|[icon](https://en.wikipedia.org/wiki/File:Question_book-new.svg) |This section **does not [cite](https://en.wikipedia.org/wiki/Wikipedia:Citing_sources "Wikipedia:Citing sources") any [sources](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability")** . Please help [improve this section](https://en.wikipedia.org/wiki/Special:EditPage/Extract,_transform,_load "Special:EditPage/Extract, transform, load") by [adding citations to reliable sources](https://en.wikipedia.org/wiki/Help:Referencing_for_beginners "Help:Referencing for beginners") . Unsourced material may be challenged and [removed](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") . _( September 2024 )_ _( [Learn how and when to remove this message](https://en.wikipedia.org/wiki/Help:Maintenance_template_removal "Help:Maintenance template removal") )_ |
| --- | --- |

### Extract

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=2 "Edit section: Extract") ]

ETL processing involves extracting the data from the source system(s). In many cases, this represents the most important aspect of ETL, since extracting data correctly sets the stage for the success of subsequent processes. Most data-warehousing projects combine data from different source systems. Each separate system may also use a different data organization and/or [format](https://en.wikipedia.org/wiki/File_format "File format") . [[ 5 ]](:0-5) Common data-source formats include [relational databases](https://en.wikipedia.org/wiki/Relational_database "Relational database") , [flat-file databases](https://en.wikipedia.org/wiki/Flat-file_database "Flat-file database") , [XML](https://en.wikipedia.org/wiki/XML "XML") , and [JSON](https://en.wikipedia.org/wiki/JSON "JSON") , but may also include non-relational database structures such as [IBM Information Management System](https://en.wikipedia.org/wiki/IBM_Information_Management_System "IBM Information Management System") or other data structures such as [Virtual Storage Access Method (VSAM)](https://en.wikipedia.org/wiki/Virtual_Storage_Access_Method "Virtual Storage Access Method") or [Indexed Sequential Access Method (ISAM)](https://en.wikipedia.org/wiki/ISAM "ISAM") , or even formats fetched from outside sources by means such as a [web crawler](https://en.wikipedia.org/wiki/Web_crawler "Web crawler") or [data scraping](https://en.wikipedia.org/wiki/Data_scraping "Data scraping") . [[ 5 ]](:0-5) The streaming of the extracted data source and loading on-the-fly to the destination database is another way of performing ETL when no intermediate data storage is required. [[ 6 ]](:1-6)

An intrinsic part of the extraction involves data validation to confirm whether the data pulled from the sources has the correct/expected values in a given domain (such as a pattern/default or list of values). If the data fails the validation rules, it is rejected entirely or in part. [[ 7 ]]() The rejected data is ideally reported back to the source system for further analysis to identify and to rectify incorrect records or perform [data wrangling](https://en.wikipedia.org/wiki/Data_wrangling "Data wrangling") .

### Transform

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=3 "Edit section: Transform") ]

In the [data transformation](https://en.wikipedia.org/wiki/Data_transformation "Data transformation") stage, a series of rules or functions are applied to the extracted data in order to prepare it for loading into the end target. [[ 5 ]](:0-5) [[ 6 ]](:1-6)

An important function of transformation is [data cleansing](https://en.wikipedia.org/wiki/Data_cleansing "Data cleansing") , which aims to pass only "proper" data to the target. The challenge when different systems interact is in the relevant systems' interfacing and communicating. Character sets that may be available in one system may not be in others. [[ 8 ]]()

In other cases, one or more of the following transformation types may be required to meet the business and technical needs of the server or data warehouse: [[ 9 ]]()

* Selecting only certain columns to load (or selecting [null](https://en.wikipedia.org/wiki/Null_\(SQL\) "Null (SQL)") columns not to load). For example, if the source data has three columns (aka "attributes"), roll\_no, age, and salary, then the selection may take only roll\_no and salary. Or, the selection mechanism may ignore all those records where salary is not present (salary = null).
* Translating coded values. For example if the source system codes male as "1" and female as "2", but the warehouse codes male as "M" and female as "F".
* Encoding free-form values. For example, mapping "Male" to "M".
* Deriving a new calculated value. For example, `sale_amount = qty * unit_price` .
* Sorting or ordering the data based on a list of columns to improve search performance.
* [Joining](https://en.wikipedia.org/wiki/Join_\(relational_algebra\) "Join (relational algebra)") data from multiple sources ( _e.g._ , lookup, merge) and [deduplicating](https://en.wikipedia.org/wiki/Record_linkage "Record linkage") the data.
* Aggregating. For example, rollup – summarizing multiple rows of data – total sales for each store, and for each region, etc.
* Generating [surrogate-key](https://en.wikipedia.org/wiki/Surrogate_key "Surrogate key") values.
* [Transposing](https://en.wikipedia.org/wiki/Transpose "Transpose") or [pivoting](https://en.wikipedia.org/wiki/Pivot_table "Pivot table") (turning multiple columns into multiple rows or vice versa).
* Splitting a column into multiple columns. For example, converting a [comma-separated list](https://en.wikipedia.org/wiki/Comma_separated_values "Comma separated values") , specified as a string in one column, into individual values in different columns.
* Disaggregating repeating columns.
* Looking up and validating the relevant data from tables or referential files.
* Applying any form of data validation. Failed validation may result in a full rejection of the data, partial rejection, or no rejection at all, and thus none, some, or all of the data are handed over to the next step depending on the rule design and exception handling; many of the above transformations may result in exceptions, e.g., when a code translation parses an unknown code in the extracted data.

### Load

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=4 "Edit section: Load") ]

The load phase loads the data into the end target, which can be any data store including a simple delimited flat file or a [data warehouse](https://en.wikipedia.org/wiki/Data_warehouse "Data warehouse") . Depending on the requirements of the organization, this process varies widely. Some data warehouses may overwrite existing information with cumulative information; updating extracted data is frequently done on a daily, weekly, or monthly basis. Other data warehouses (or even other parts of the same data warehouse) may add new data in a historical form at regular intervals – for example, hourly. To understand this, consider a data warehouse that is required to maintain sales records of the last year. This data warehouse overwrites any data older than a year with newer data. However, the entry of data for any one year window is made in a historical manner. The timing and scope to replace or append are strategic design choices dependent on the time available and the [business](https://en.wikipedia.org/wiki/Business "Business") needs. More complex systems can maintain a history and [audit trail](https://en.wikipedia.org/wiki/Audit_trail "Audit trail") of all changes to the data loaded in the data warehouse.
As the load phase interacts with a database, the constraints defined in the database schema – as well as in triggers activated upon data load – apply (for example, uniqueness, [referential integrity](https://en.wikipedia.org/wiki/Referential_integrity "Referential integrity") , mandatory fields), which also contribute to the overall data quality performance of the ETL process.

* For example, a financial institution might have information on a customer in several departments and each department might have that customer's information listed in a different way. The membership department might list the customer by name, whereas the accounting department might list the customer by number. ETL can bundle all of these data elements and consolidate them into a uniform presentation, such as for storing in a database or data warehouse.
* Another way that companies use ETL is to move information to another application permanently. For instance, the new application might use another database vendor and most likely a very different database schema. ETL can be used to transform the data into a format suitable for the new application to use.
* An example would be an [expense and cost recovery system](https://en.wikipedia.org/wiki/Expense_and_cost_recovery_system "Expense and cost recovery system") such as used by [accountants](https://en.wikipedia.org/wiki/Accounting "Accounting") , [consultants](https://en.wikipedia.org/wiki/Consultant "Consultant") , and [law firms](https://en.wikipedia.org/wiki/Law_firm "Law firm") . The data usually ends up in the [time and billing system](https://en.wikipedia.org/wiki/Law_practice_management_software "Law practice management software") , although some businesses may also utilize the raw data for employee productivity reports to Human Resources (personnel dept.) or equipment usage reports to Facilities Management.

### Additional phases

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=5 "Edit section: Additional phases") ]

A real-life ETL cycle may consist of additional execution steps, for example:

1. Cycle initiation (pre-ETL: Ensure all ETL-relevant systems are available, functional, and have no issues that would suddenly halt an hour into ETL, such as valid [B2B](https://en.wikipedia.org/wiki/Business-to-business "Business-to-business") compute/memory/storage subscriptions and API keys, satisfactory budget for estimated time/money, no higher-priority tasks)
2. Build [reference data](https://en.wikipedia.org/wiki/Reference_data "Reference data") (i.e., linking ( _not hard-copying_ ) to reliable historic baselines)
3. Extract (from data sources)
4. [Validate](https://en.wikipedia.org/wiki/Data_validation "Data validation") (ensure data can _eventually_ be useful; data is not 100% garbage)
5. Transform ( [clean](https://en.wikipedia.org/wiki/Data_cleaning "Data cleaning") , apply [business rules](https://en.wikipedia.org/wiki/Business_rule "Business rule") , check for [data integrity](https://en.wikipedia.org/wiki/Data_integrity "Data integrity") , create [aggregates](https://en.wikipedia.org/wiki/Aggregate_\(data_warehouse\) "Aggregate (data warehouse)") or disaggregates)
6. Stage (load into [staging](https://en.wikipedia.org/wiki/Staging_\(data\) "Staging (data)") tables, if used)
7. [Audit reports](https://en.wikipedia.org/wiki/Audit_report "Audit report") (for example, on compliance with business rules. Also, in case of failure, helps to diagnose/repair)
8. Publish (to target tables)
9. [Archive](https://en.wikipedia.org/wiki/Archiving "Archiving") (Extreme, space-efficient compression for very rarely used, old data. Situationally, can be [lossy](https://en.wikipedia.org/wiki/Lossy "Lossy") )

## Design challenges

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=6 "Edit section: Design challenges") ]

ETL processes can involve considerable complexity, and significant operational problems can occur with improperly designed ETL systems.

### Data variations

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=7 "Edit section: Data variations") ]

The range of data values or data quality in an operational system may exceed the expectations of designers at the time validation and transformation rules are specified. [Data profiling](https://en.wikipedia.org/wiki/Data_profiling "Data profiling") of a source during data analysis can identify the data conditions that must be managed by transform rules specifications, leading to an amendment of validation rules explicitly and implicitly implemented in the ETL process.

Data warehouses are typically assembled from a variety of data sources with different formats and purposes. As such, ETL is a key process to bring all the data together in a standard, homogeneous environment.

Design analysis [[ 10 ]]() should establish the [scalability](https://en.wikipedia.org/wiki/Scalability "Scalability") of an ETL system across the lifetime of its usage – including understanding the volumes of data that must be processed within [service level agreements](https://en.wikipedia.org/wiki/Service_level_agreement "Service level agreement") . The time available to extract from source systems may change, which may mean the same amount of data may have to be processed in less time. Some ETL systems have to scale to process terabytes of data to update data warehouses with tens of terabytes of data. Increasing volumes of data may require designs that can scale from daily [batch](https://en.wikipedia.org/wiki/Batch_processing "Batch processing") to multiple-day micro batch to integration with [message queues](https://en.wikipedia.org/wiki/Message_queue "Message queue") or real-time change-data-capture for continuous transformation and update.

### Uniqueness of keys

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=8 "Edit section: Uniqueness of keys") ]

[Unique keys](https://en.wikipedia.org/wiki/Unique_key "Unique key") play an important part in all relational databases, as they tie everything together. A unique key is a column that identifies a given entity, whereas a [foreign key](https://en.wikipedia.org/wiki/Foreign_key "Foreign key") is a column in another table that refers to a primary key. Keys can comprise several columns, in which case they are composite keys. In many cases, the primary key is an auto-generated integer that has no meaning for the [business entity](https://en.wikipedia.org/wiki/Business_entity_\(computer_science\) "Business entity (computer science)") being represented, but solely exists for the purpose of the relational database – commonly referred to as a [surrogate key](https://en.wikipedia.org/wiki/Surrogate_key "Surrogate key") .

As there is usually more than one data source getting loaded into the warehouse, the keys are an important concern to be addressed. For example: customers might be represented in several data sources, with their [Social Security number](https://en.wikipedia.org/wiki/Social_Security_number "Social Security number") as the primary key in one source, their phone number in another, and a surrogate in the third. Yet a data warehouse may require the consolidation of all the customer information into one [dimension](https://en.wikipedia.org/wiki/Dimension_\(data_warehouse\) "Dimension (data warehouse)") .

A recommended way to deal with the concern involves adding a warehouse surrogate key, which is used as a foreign key from the fact table. [[ 11 ]]()

Usually, updates occur to a dimension's source data, which must be reflected in the data warehouse.

If the primary key of the source data is required for reporting, the dimension already contains that piece of information for each row. If the source data uses a surrogate key, the warehouse must keep track of it even though it is never used in queries or reports; it is done by creating a [lookup table](https://en.wikipedia.org/wiki/Lookup_table "Lookup table") that contains the warehouse surrogate key and the originating key. [[ 12 ]](,_Data_Warehouse_Design_p._291-12) This way, the dimension is not polluted with surrogates from various source systems, while the ability to update is preserved.

The lookup table is used in different ways depending on the nature of the source data.
There are 5 types to consider; [[ 12 ]](,_Data_Warehouse_Design_p._291-12) three are included here:

Type 1
    The dimension row is simply updated to match the current state of the source system; the warehouse does not capture history; the lookup table is used to identify the dimension row to update or overwrite
Type 2
    A new dimension row is added with the new state of the source system; a new surrogate key is assigned; source key is no longer unique in the lookup table
Fully logged
    A new dimension row is added with the new state of the source system, while the previous dimension row is updated to reflect it is no longer active and time of deactivation.

### Performance

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=9 "Edit section: Performance") ]

|[icon](https://en.wikipedia.org/wiki/File:Question_book-new.svg) |This section **does not [cite](https://en.wikipedia.org/wiki/Wikipedia:Citing_sources "Wikipedia:Citing sources") any [sources](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability")** . Please help [improve this section](https://en.wikipedia.org/wiki/Special:EditPage/Extract,_transform,_load "Special:EditPage/Extract, transform, load") by [adding citations to reliable sources](https://en.wikipedia.org/wiki/Help:Referencing_for_beginners "Help:Referencing for beginners") . Unsourced material may be challenged and [removed](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") . _( September 2024 )_ _( [Learn how and when to remove this message](https://en.wikipedia.org/wiki/Help:Maintenance_template_removal "Help:Maintenance template removal") )_ |
| --- | --- |

ETL vendors benchmark their record-systems at multiple TB (terabytes) per hour (or ~1 GB per second) using powerful servers with multiple CPUs, multiple hard drives, multiple gigabit-network connections, and much memory.

In real life, the slowest part of an ETL process usually occurs in the database load phase. Databases may perform slowly because they have to take care of concurrency, integrity maintenance, and indices. Thus, for better performance, it may make sense to employ:

* _Direct path extract_ method or bulk unload whenever is possible (instead of querying the database) to reduce the load on source system while getting high-speed extract
* Most of the transformation processing outside of the database
* Bulk load operations whenever possible

Still, even using bulk operations, database access is usually the bottleneck in the ETL process. Some common methods used to increase performance are:

* [Partition](https://en.wikipedia.org/wiki/Partition_\(database\) "Partition (database)") tables (and indices): try to keep partitions similar in size (watch for `null` values that can skew the partitioning)
* Do all validation in the ETL layer before the load: disable [integrity](https://en.wikipedia.org/wiki/Data_integrity "Data integrity") checking ( `disable constraint` ...) in the target database tables during the load
* Disable [triggers](https://en.wikipedia.org/wiki/Database_trigger "Database trigger") ( `disable trigger` ...) in the target database tables during the load: simulate their effect as a separate step
* Generate IDs in the ETL layer (not in the database)
* Drop the [indices](https://en.wikipedia.org/wiki/Database_index "Database index") (on a table or partition) before the load – and recreate them after the load (SQL: `drop index` ... `; create index` ...)
* Use parallel bulk load when possible – works well when the table is partitioned or there are no indices (Note: attempting to do parallel loads into the same table (partition) usually causes locks – if not on the data rows, then on indices)
* If a requirement exists to do insertions, updates, or deletions, find out which rows should be processed in which way in the ETL layer, and then process these three operations in the database separately; you often can do bulk load for inserts, but updates and deletes commonly go through an [API](https://en.wikipedia.org/wiki/API "API") (using [SQL](https://en.wikipedia.org/wiki/SQL "SQL") )

Whether to do certain operations in the database or outside may involve a trade-off. For example, removing duplicates using `distinct` may be slow in the database; thus, it makes sense to do it outside. On the other side, if using `distinct` significantly (x100) decreases the number of rows to be extracted, then it makes sense to remove duplications as early as possible in the database before unloading data.

A common source of problems in ETL is a big number of dependencies among ETL jobs. For example, job "B" cannot start while job "A" is not finished. One can usually achieve better performance by visualizing all processes on a graph, and trying to reduce the graph making maximum use of [parallelism](https://en.wikipedia.org/wiki/Parallel_computing "Parallel computing") , and making "chains" of consecutive processing as short as possible. Again, partitioning of big tables and their indices can really help.

Another common issue occurs when the data are spread among several databases, and processing is done in those databases sequentially. Sometimes database replication may be involved as a method of copying data between databases – it can significantly slow down the whole process. The common solution is to reduce the processing graph to only three layers:

* Sources
* Central ETL layer
* Targets

This approach allows processing to take maximum advantage of parallelism. For example, if you need to load data into two databases, you can run the loads in parallel (instead of loading into the first – and then replicating into the second).

Sometimes processing must take place sequentially. For example, dimensional (reference) data are needed before one can get and validate the rows for main ["fact" tables](https://en.wikipedia.org/wiki/Fact_table "Fact table") .

### Parallel computing

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=10 "Edit section: Parallel computing") ]

|[icon](https://en.wikipedia.org/wiki/File:Question_book-new.svg) |This section **does not [cite](https://en.wikipedia.org/wiki/Wikipedia:Citing_sources "Wikipedia:Citing sources") any [sources](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability")** . Please help [improve this section](https://en.wikipedia.org/wiki/Special:EditPage/Extract,_transform,_load "Special:EditPage/Extract, transform, load") by [adding citations to reliable sources](https://en.wikipedia.org/wiki/Help:Referencing_for_beginners "Help:Referencing for beginners") . Unsourced material may be challenged and [removed](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") . _( September 2024 )_ _( [Learn how and when to remove this message](https://en.wikipedia.org/wiki/Help:Maintenance_template_removal "Help:Maintenance template removal") )_ |
| --- | --- |

Some ETL software implementations include [parallel processing](https://en.wikipedia.org/wiki/Parallel_computing "Parallel computing") . This enables a number of methods to improve overall performance of ETL when dealing with large volumes of data.

ETL applications implement three main types of parallelism:

* Data: By splitting a single sequential file into smaller data files to provide [parallel access](https://en.wikipedia.org/wiki/Parallel_Random_Access_Machine "Parallel Random Access Machine")
* [Pipeline](https://en.wikipedia.org/wiki/Pipeline_\(computing\) "Pipeline (computing)") : allowing the simultaneous running of several components on the same [data stream](https://en.wikipedia.org/wiki/Data_stream "Data stream") , e.g. looking up a value on record 1 at the same time as adding two fields on record 2
* Component: The simultaneous running of multiple [processes](https://en.wikipedia.org/wiki/Process_\(computing\) "Process (computing)") on different data streams in the same job, e.g. sorting one input file while removing duplicates on another file

All three types of parallelism usually operate combined in a single job or task.

An additional difficulty comes with making sure that the data being uploaded is relatively consistent. Because multiple source databases may have different update cycles (some may be updated every few minutes, while others may take days or weeks), an ETL system may be required to hold back certain data until all sources are synchronized. Likewise, where a warehouse may have to be reconciled to the contents in a source system or with the general ledger, establishing synchronization and reconciliation points becomes necessary.

### Failure recovery

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=11 "Edit section: Failure recovery") ]

|[icon](https://en.wikipedia.org/wiki/File:Question_book-new.svg) |This section **does not [cite](https://en.wikipedia.org/wiki/Wikipedia:Citing_sources "Wikipedia:Citing sources") any [sources](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability")** . Please help [improve this section](https://en.wikipedia.org/wiki/Special:EditPage/Extract,_transform,_load "Special:EditPage/Extract, transform, load") by [adding citations to reliable sources](https://en.wikipedia.org/wiki/Help:Referencing_for_beginners "Help:Referencing for beginners") . Unsourced material may be challenged and [removed](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") . _( September 2024 )_ _( [Learn how and when to remove this message](https://en.wikipedia.org/wiki/Help:Maintenance_template_removal "Help:Maintenance template removal") )_ |
| --- | --- |

Data warehousing procedures usually subdivide a big ETL process into smaller pieces running sequentially or in parallel. To keep track of data flows, it makes sense to tag each data row with "row\_id", and tag each piece of the process with "run\_id". In case of a failure, having these IDs help to roll back and rerun the failed piece.

Best practice also calls for _checkpoints_ , which are states when certain phases of the process are completed. Once at a checkpoint, it is a good idea to write everything to disk, clean out some temporary files, log the state, etc.

## Implementations

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=12 "Edit section: Implementations") ]

An established ETL framework may improve connectivity and [scalability](https://en.wikipedia.org/wiki/Scalability "Scalability") . [ _[citation needed](https://en.wikipedia.org/wiki/Wikipedia:Citation_needed "Wikipedia:Citation needed")_ ] A good ETL tool must be able to communicate with the many different [relational databases](https://en.wikipedia.org/wiki/Relational_database "Relational database") and read the various file formats used throughout an organization. ETL tools have started to migrate into [enterprise application integration](https://en.wikipedia.org/wiki/Enterprise_application_integration "Enterprise application integration") , or even [enterprise service bus](https://en.wikipedia.org/wiki/Enterprise_service_bus "Enterprise service bus") , systems that now cover much more than just the extraction, transformation, and loading of data. Many ETL vendors now have [data profiling](https://en.wikipedia.org/wiki/Data_profiling "Data profiling") , [data quality](https://en.wikipedia.org/wiki/Data_quality "Data quality") , and [metadata](https://en.wikipedia.org/wiki/Metadata_\(computing\) "Metadata (computing)") capabilities. A common use case for ETL tools include converting [CSV](https://en.wikipedia.org/wiki/Comma-separated_values "Comma-separated values") files to formats readable by relational databases. A typical translation of millions of records is facilitated by ETL tools that enable users to input CSV-like data feeds/files and import them into a database with as little code as possible.

ETL tools are typically used by a broad range of professionals – from students in computer science looking to quickly import large data sets to database architects in charge of company account management, ETL tools have become a convenient tool that can be relied on to get maximum performance. ETL tools in most cases contain a GUI that helps users conveniently transform data, using a visual data mapper, as opposed to writing large programs to parse files and modify data types.

While ETL tools have traditionally been for developers and IT staff, research firm Gartner wrote that the new trend is to provide these capabilities to business users so they can themselves create connections and data integrations when needed, rather than going to the IT staff. [[ 13 ]]() Gartner refers to these non-technical users as Citizen Integrators. [[ 14 ]]()

## Variations

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=13 "Edit section: Variations") ]

### In online transaction processing

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=14 "Edit section: In online transaction processing") ]

[ETL diagram in the context of online transaction processing](https://en.wikipedia.org/wiki/File:Conventional_ETL_Diagram.jpg) ETL diagram in the context of [online transaction processing](https://en.wikipedia.org/wiki/Online_transaction_processing "Online transaction processing") [[ 1 ]]()

In [online transaction processing](https://en.wikipedia.org/wiki/Online_transaction_processing "Online transaction processing") (OLTP) applications, changes from individual OLTP instances are detected and logged into a snapshot, or batch, of updates. An ETL instance can be used to periodically collect all of these batches, transform them into a common format, and load them into a data lake or warehouse. [[ 1 ]]()

### Virtual ETL

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=15 "Edit section: Virtual ETL") ]

|[icon](https://en.wikipedia.org/wiki/File:Question_book-new.svg) |This section **does not [cite](https://en.wikipedia.org/wiki/Wikipedia:Citing_sources "Wikipedia:Citing sources") any [sources](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability")** . Please help [improve this section](https://en.wikipedia.org/wiki/Special:EditPage/Extract,_transform,_load "Special:EditPage/Extract, transform, load") by [adding citations to reliable sources](https://en.wikipedia.org/wiki/Help:Referencing_for_beginners "Help:Referencing for beginners") . Unsourced material may be challenged and [removed](https://en.wikipedia.org/wiki/Wikipedia:Verifiability "Wikipedia:Verifiability") . _( September 2024 )_ _( [Learn how and when to remove this message](https://en.wikipedia.org/wiki/Help:Maintenance_template_removal "Help:Maintenance template removal") )_ |
| --- | --- |

[Data virtualization](https://en.wikipedia.org/wiki/Data_virtualization "Data virtualization") can be used to advance ETL processing. The application of data virtualization to ETL allowed solving the most common ETL tasks of [data migration](https://en.wikipedia.org/wiki/Data_migration "Data migration") and application integration for multiple dispersed data sources. Virtual ETL operates with the abstracted representation of the objects or entities gathered from the variety of relational, semi-structured, and [unstructured data](https://en.wikipedia.org/wiki/Unstructured_data "Unstructured data") sources. ETL tools can leverage object-oriented modeling and work with entities' representations persistently stored in a centrally located [hub-and-spoke](https://en.wikipedia.org/wiki/Hub-and-spoke "Hub-and-spoke") architecture. Such a collection that contains representations of the entities or objects gathered from the data sources for ETL processing is called a metadata repository and it can reside in memory or be made persistent. By using a persistent metadata repository, ETL tools can transition from one-time projects to persistent middleware, performing data harmonization and [data profiling](https://en.wikipedia.org/wiki/Data_profiling "Data profiling") consistently and in near-real time.

### Extract, load, transform (ELT)

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=16 "Edit section: Extract, load, transform (ELT)") ]

Main article: [Extract, load, transform](https://en.wikipedia.org/wiki/Extract,_load,_transform "Extract, load, transform")

[Extract, load, transform](https://en.wikipedia.org/wiki/Extract,_load,_transform "Extract, load, transform") (ELT) is a variant of ETL where the extracted data is loaded into the target system first. [[ 15 ]]() The architecture for the analytics pipeline shall also consider where to cleanse and enrich data [[ 15 ]]() as well as how to conform dimensions. [[ 1 ]]() Some of the benefits of an ELT process include speed and the ability to more easily handle both unstructured and structured data. [[ 16 ]]()

[Ralph Kimball](https://en.wikipedia.org/wiki/Ralph_Kimball "Ralph Kimball") and [Joe Caserta](https://en.wikipedia.org/wiki/Joe_Caserta "Joe Caserta") 's book _The Data Warehouse ETL Toolkit_ , (Wiley, 2004), which is used as a textbook for courses teaching ETL processes in data warehousing, addressed this issue. [[ 17 ]]()

Cloud-based data warehouses like [Amazon Redshift](https://en.wikipedia.org/wiki/Amazon_Redshift "Amazon Redshift") , Google [BigQuery](https://en.wikipedia.org/wiki/BigQuery "BigQuery") , [Microsoft Azure Synapse Analytics](https://en.wikipedia.org/wiki/Microsoft_Azure_Synapse_Analytics?action=edit&redlink=1 "Microsoft Azure Synapse Analytics (page does not exist)") , and [Snowflake](https://en.wikipedia.org/wiki/Snowflake_Inc. "Snowflake Inc.") provide highly scalable computing power. This lets businesses forgo preload transformations and replicate raw data into their data warehouses, where it can transform them as needed using [SQL](https://en.wikipedia.org/wiki/SQL "SQL") .

After having used ELT, data may be processed further and stored in a data mart. [[ 18 ]]()

Most data integration tools skew towards ETL, while ELT is popular in database and data warehouse appliances. Similarly, it is possible to perform TEL (Transform, Extract, Load) where data is first transformed on a blockchain (as a way of recording changes to data, e.g., token burning) before extracting and loading into another data store. [[ 19 ]]()

## See also

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=17 "Edit section: See also") ]

* [Architectural pattern](https://en.wikipedia.org/wiki/Architectural_pattern "Architectural pattern") (EA reference architecture)
* [CMS Pipelines](https://en.wikipedia.org/wiki/CMS_Pipelines "CMS Pipelines")
* [Create, read, update and delete](https://en.wikipedia.org/wiki/Create,_read,_update_and_delete "Create, read, update and delete") (CRUD)
* [Data cleansing](https://en.wikipedia.org/wiki/Data_cleansing "Data cleansing")
* [Data integration](https://en.wikipedia.org/wiki/Data_integration "Data integration")
* [Data mesh](https://en.wikipedia.org/wiki/Data_mesh "Data mesh") , a domain-oriented data architecture
* [Data migration](https://en.wikipedia.org/wiki/Data_migration "Data migration")
* [Data transformation (computing)](https://en.wikipedia.org/wiki/Data_transformation_\(computing\) "Data transformation (computing)")
* [Electronic data interchange](https://en.wikipedia.org/wiki/Electronic_data_interchange "Electronic data interchange") (EDI)
* [Enterprise architecture](https://en.wikipedia.org/wiki/Enterprise_architecture "Enterprise architecture")
* [Legal Electronic Data Exchange Standard](https://en.wikipedia.org/wiki/Legal_Electronic_Data_Exchange_Standard "Legal Electronic Data Exchange Standard") (LEDES)
* [Metadata discovery](https://en.wikipedia.org/wiki/Metadata_discovery "Metadata discovery")
* [Online analytical processing](https://en.wikipedia.org/wiki/Online_analytical_processing "Online analytical processing") (OLAP)
* [Online transaction processing](https://en.wikipedia.org/wiki/Online_transaction_processing "Online transaction processing") (OLTP)
* [Spatial ETL](https://en.wikipedia.org/wiki/Spatial_ETL "Spatial ETL")

## References

[ [edit](https://en.wikipedia.org/w/index.php?title=Extract,_transform,_load&action=edit&section=18 "Edit section: References") ]

1. 1 2 3 4 Ralph., Kimball (2004). _The data warehouse ETL toolkit : practical techniques for extracting, cleaning, conforming, and delivering data_ . Caserta, Joe, 1965-. Indianapolis, IN: Wiley. [ISBN](https://en.wikipedia.org/wiki/ISBN_\(identifier\) "ISBN (identifier)") [978-0764579233](https://en.wikipedia.org/wiki/Special:BookSources/978-0764579233 "Special:BookSources/978-0764579233") . [OCLC](https://en.wikipedia.org/wiki/OCLC_\(identifier\) "OCLC (identifier)") [57301227](https://search.worldcat.org/oclc/57301227) .
2. ↑ Denney, MJ (2016). ["Validating the extract, transform, load process used to populate a large clinical research database"](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5556907) . _International Journal of Medical Informatics_ . **94** : 271– 4\. [doi](https://en.wikipedia.org/wiki/Doi_\(identifier\) "Doi (identifier)") : [10\.1016/j.ijmedinf.2016.07.009](https://doi.org/10.1016%2Fj.ijmedinf.2016.07.009) . [PMC](https://en.wikipedia.org/wiki/PMC_\(identifier\) "PMC (identifier)") [5556907](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5556907) . [PMID](https://en.wikipedia.org/wiki/PMID_\(identifier\) "PMID (identifier)") [27506144](https://pubmed.ncbi.nlm.nih.gov/27506144) .
3. ↑ Zhao, Shirley (2017-10-20). ["What is ETL? (Extract, Transform, Load) | Experian"](https://www.edq.com/blog/what-is-etl-extract-transform-load/) . _Experian Data Quality_ . Retrieved 2018-12-12 .
4. ↑ Pott, Trevor (4 June 2018). ["Extract, transform, load? More like extremely tough to load, amirite?"](https://www.theregister.co.uk/2018/06/04/data_integration_is_hard/) . _[The Register](https://en.wikipedia.org/wiki/The_Register "The Register")_ . Retrieved 2018-12-12 .
5. 1 2 3 ["What is ETL (Extract, Transform, Load)?"](https://www.ibm.com/think/topics/etl) . _www.ibm.com_ . IBM. 2021-10-04 . Retrieved 2026-05-31 . `{{ [cite web](https://en.wikipedia.org/wiki/Template:Cite_web "Template:Cite web") }}` : CS1 maint: url-status ( [link](https://en.wikipedia.org/wiki/Category:CS1_maint:_url-status "Category:CS1 maint: url-status") )
6. 1 2 ["Extract, transform, load (ETL) - Azure Architecture Center"](https://learn.microsoft.com/en-us/azure/architecture/data-guide/relational-data/etl) . _learn.microsoft.com_ . Microsoft . Retrieved 2026-05-31 . `{{ [cite web](https://en.wikipedia.org/wiki/Template:Cite_web "Template:Cite web") }}` : CS1 maint: url-status ( [link](https://en.wikipedia.org/wiki/Category:CS1_maint:_url-status "Category:CS1 maint: url-status") )
7. ↑ Tobin, Donal. ["Data Validation in ETL - 2026 Guide"](https://www.integrate.io/blog/data-validation-etl/) . _Integrate.io_ . Retrieved 2026-05-31 .
8. ↑ Tobin, Donal. ["What is Data Cleansing and Why Does it Matter?"](https://www.integrate.io/blog/what-does-data-cleansing-entail-and-why-does-it-matter/) . _Integrate.io_ . Retrieved 2026-05-31 .
9. ↑ ["What are the Different Types of ETL Data Transformation | Rivery"](https://web.archive.org/web/20260212090737/https://rivery.io/data-learning-center/types-of-etl-data-transformation/) . _Rivery_ . Archived from [the original](https://rivery.io/data-learning-center/types-of-etl-data-transformation/) on 2026-02-12 . Retrieved 2026-05-31 .
10. ↑ Theodorou, Vasileios (2017). "Frequent patterns in ETL workflows: An empirical approach". _Data & Knowledge Engineering_ . **112** : 1– 16\. [doi](https://en.wikipedia.org/wiki/Doi_\(identifier\) "Doi (identifier)") : [10\.1016/j.datak.2017.08.004](https://doi.org/10.1016%2Fj.datak.2017.08.004) . [hdl](https://en.wikipedia.org/wiki/Hdl_\(identifier\) "Hdl (identifier)") : [2117/110172](https://hdl.handle.net/2117%2F110172) .
11. ↑ Kimball, The Data Warehouse Lifecycle Toolkit, p. 332
12. 1 2 Golfarelli/Rizzi, Data Warehouse Design, p. 291
13. ↑ ["The Inexorable Rise of Self Service Data Integration"](http://blogs.gartner.com/andrew_white/2015/05/22/the-inexorable-rise-of-self-service-data-integration/) . _Gartner_ . 22 May 2015 . Retrieved 31 January 2016 .
14. ↑ ["Embrace the Citizen Integrator"](https://www.gartner.com/doc/2891817/embrace-citizen-integrator-approach-improve) . _Gartner_ . Retrieved September 29, 2021 .
15. 1 2 Amazon Web Services, Data Warehousing on AWS, p. 9
16. ↑ Mishra, Tanya (2023-09-02). ["ETL vs ELT: Meaning, Major Differences & Examples"](https://www.analyticsinsight.net/etl-vs-elt-meaning-major-differences-examples/) . _Analytics Insight_ . Retrieved 2024-01-30 .
17. ↑ ["The Data Warehouse ETL Toolkit: Practical Techniques for Extracting, Cleaning, Conforming, and Delivering Data [ Book ] "](https://www.oreilly.com/library/view/the-data-warehouse/9780764567575/) .
18. ↑ Amazon Web Services, Data Warehousing on AWS, 2016, p. 10
19. ↑ Bandara, H. M. N. Dilum; Xu, Xiwei; Weber, Ingo (2020). "Patterns for Blockchain Data Migration". _Proceedings of the European Conference on Pattern Languages of Programs 2020_ . pp. 1– 19\. [arXiv](https://en.wikipedia.org/wiki/ArXiv_\(identifier\) "ArXiv (identifier)") : [1906\.00239](https://arxiv.org/abs/1906.00239) . [doi](https://en.wikipedia.org/wiki/Doi_\(identifier\) "Doi (identifier)") : [10\.1145/3424771.3424796](https://doi.org/10.1145%2F3424771.3424796) . [ISBN](https://en.wikipedia.org/wiki/ISBN_\(identifier\) "ISBN (identifier)") [9781450377690](https://en.wikipedia.org/wiki/Special:BookSources/9781450377690 "Special:BookSources/9781450377690") . [S2CID](https://en.wikipedia.org/wiki/S2CID_\(identifier\) "S2CID (identifier)") [219956181](https://api.semanticscholar.org/CorpusID:219956181) .

|* [v](https://en.wikipedia.org/wiki/Template:Data "Template:Data")
* [t](https://en.wikipedia.org/wiki/Template_talk:Data "Template talk:Data")
* [e](https://en.wikipedia.org/wiki/Special:EditPage/Template:Data "Special:EditPage/Template:Data")

[Data](https://en.wikipedia.org/wiki/Data "Data") |
| --- | --- |
|Information, data, and value |* [Information](https://en.wikipedia.org/wiki/Information "Information")
* [Meta](https://en.wikipedia.org/wiki/Metadata "Metadata")
* [Type](https://en.wikipedia.org/wiki/Data_type "Data type")
* [Structure](https://en.wikipedia.org/wiki/Data_structure "Data structure")
* [Ecosystem](https://en.wikipedia.org/wiki/Data_ecosystem "Data ecosystem")
* [Library](https://en.wikipedia.org/wiki/Data_library "Data library")
* [Infrastructure](https://en.wikipedia.org/wiki/Data_infrastructure "Data infrastructure")
* [Value](https://en.wikipedia.org/wiki/Value_of_information "Value of information") |
|Data categories and semantic structure |* Data categories
* [Master data](https://en.wikipedia.org/wiki/Master_data "Master data")
* [Master data management](https://en.wikipedia.org/wiki/Master_data_management "Master data management")
* [Reference data](https://en.wikipedia.org/wiki/Reference_data "Reference data")
* [Transaction data](https://en.wikipedia.org/wiki/Transaction_data "Transaction data")
* Analytical data
* [Metadata](https://en.wikipedia.org/wiki/Metadata "Metadata")
* [Code tables](https://en.wikipedia.org/wiki/Code_\(metadata\) "Code (metadata)")
* [Controlled vocabulary](https://en.wikipedia.org/wiki/Controlled_vocabulary "Controlled vocabulary")
* Crosswalks
* [Hierarchies](https://en.wikipedia.org/wiki/Data_hierarchy "Data hierarchy")
* Observation data
* [Dark data](https://en.wikipedia.org/wiki/Dark_data "Dark data")
* [Trade and market data](https://en.wikipedia.org/wiki/Marketing_information_system "Marketing information system") |
|Data management and governance |* [Management](https://en.wikipedia.org/wiki/Data_management "Data management")
* [Governance](https://en.wikipedia.org/wiki/Data_governance "Data governance")
  
    + [Cooperatives](https://en.wikipedia.org/wiki/Data_cooperative "Data cooperative")
* [Ethics](https://en.wikipedia.org/wiki/Data_ethics "Data ethics")
* [Stewardship](https://en.wikipedia.org/wiki/Data_steward "Data steward")
* [Lineage](https://en.wikipedia.org/wiki/Data_lineage "Data lineage")
* [Curation](https://en.wikipedia.org/wiki/Data_curation "Data curation")
* [Localization](https://en.wikipedia.org/wiki/Data_localization "Data localization")
* [Preservation](https://en.wikipedia.org/wiki/Data_preservation "Data preservation")
* [Retention](https://en.wikipedia.org/wiki/Data_retention "Data retention")
* [Publishing](https://en.wikipedia.org/wiki/Data_publishing "Data publishing")
  
    + [Open data](https://en.wikipedia.org/wiki/Open_data "Open data")
* [Master data management](https://en.wikipedia.org/wiki/Master_data_management "Master data management")
* [Reference data](https://en.wikipedia.org/wiki/Reference_data "Reference data") |
|Data quality, trust, and protection |* [Quality](https://en.wikipedia.org/wiki/Data_quality "Data quality")
* [Information quality](https://en.wikipedia.org/wiki/Information_quality "Information quality")
* [Validation](https://en.wikipedia.org/wiki/Data_validation "Data validation")
* [Cleansing](https://en.wikipedia.org/wiki/Data_cleansing "Data cleansing")
* [Scrubbing](https://en.wikipedia.org/wiki/Data_scrubbing "Data scrubbing")
* [Integrity](https://en.wikipedia.org/wiki/Data_integrity "Data integrity")
* [Protection (privacy)](https://en.wikipedia.org/wiki/Information_privacy "Information privacy")
* [Security](https://en.wikipedia.org/wiki/Data_security "Data security")
* [Anonymization](https://en.wikipedia.org/wiki/Data_anonymization "Data anonymization")
* [De-identification](https://en.wikipedia.org/wiki/Data_de-identification "Data de-identification")
* [Re-identification](https://en.wikipedia.org/wiki/Data_re-identification "Data re-identification")
* [Minimization](https://en.wikipedia.org/wiki/Data_minimization "Data minimization")
* [Erasure](https://en.wikipedia.org/wiki/Data_erasure "Data erasure")
* [Remanence](https://en.wikipedia.org/wiki/Data_remanence "Data remanence")
* [Corruption](https://en.wikipedia.org/wiki/Data_corruption "Data corruption")
* [Degradation](https://en.wikipedia.org/wiki/Data_degradation "Data degradation")
* [Loss](https://en.wikipedia.org/wiki/Data_loss "Data loss")
* [Recovery](https://en.wikipedia.org/wiki/Data_recovery "Data recovery") |
|Quality dimensions |* Accuracy
* Completeness
* Consistency
* Timeliness
* Validity
* Uniqueness
* Integrity
* Conformity
* Relevance |
|Data engineering and movement |* [Engineering](https://en.wikipedia.org/wiki/Data_engineering "Data engineering")
* [Integration](https://en.wikipedia.org/wiki/Data_integration "Data integration")
* [Storage](https://en.wikipedia.org/wiki/Data_storage "Data storage")
* [ETL](https://en.wikipedia.org/wiki/Extract,_transform,_load) / [ELT](https://en.wikipedia.org/wiki/Extract,_load,_transform "Extract, load, transform")
  
    + [Extract](https://en.wikipedia.org/wiki/Data_extraction "Data extraction")
    + [Transform](https://en.wikipedia.org/wiki/Data_transformation "Data transformation")
    + [Load](https://en.wikipedia.org/wiki/Data_loading "Data loading")
* [Migration](https://en.wikipedia.org/wiki/Data_migration "Data migration")
* [Synchronization](https://en.wikipedia.org/wiki/Data_synchronization "Data synchronization")
* [Compression](https://en.wikipedia.org/wiki/Data_compression "Data compression")
* [Fusion](https://en.wikipedia.org/wiki/Data_fusion "Data fusion")
* [Format management](https://en.wikipedia.org/wiki/Data_format_management "Data format management") |
|Data preparation and operations |* [Acquisition](https://en.wikipedia.org/wiki/Data_acquisition "Data acquisition")
* [Augmentation](https://en.wikipedia.org/wiki/Data_augmentation "Data augmentation")
* [Collection](https://en.wikipedia.org/wiki/Data_collection "Data collection")
* [Annotation](https://en.wikipedia.org/wiki/Data_annotation "Data annotation")
* [Editing](https://en.wikipedia.org/wiki/Data_editing "Data editing")
* [Deduplication](https://en.wikipedia.org/wiki/Data_deduplication "Data deduplication")
* [Pre-processing](https://en.wikipedia.org/wiki/Data_pre-processing "Data pre-processing")
* [Preparation](https://en.wikipedia.org/wiki/Data_preparation "Data preparation")
* [Processing](https://en.wikipedia.org/wiki/Data_processing "Data processing")
* [Reduction](https://en.wikipedia.org/wiki/Data_reduction "Data reduction")
* [Redundancy](https://en.wikipedia.org/wiki/Data_redundancy "Data redundancy")
* [Wrangling/munging](https://en.wikipedia.org/wiki/Data_wrangling "Data wrangling")
* [Scraping](https://en.wikipedia.org/wiki/Data_scraping "Data scraping")
* [Rescue](https://en.wikipedia.org/wiki/Data_rescue "Data rescue") |
|Analysis, science, and interpretation |* [Big](https://en.wikipedia.org/wiki/Big_data "Big data")
* [Analysis](https://en.wikipedia.org/wiki/Data_analysis "Data analysis")
* [Exploration](https://en.wikipedia.org/wiki/Data_exploration "Data exploration")
* [Mining](https://en.wikipedia.org/wiki/Data_mining "Data mining")
* [Science](https://en.wikipedia.org/wiki/Data_science "Data science")
* [Topological data analysis](https://en.wikipedia.org/wiki/Topological_data_analysis "Topological data analysis")
* [Warehouse](https://en.wikipedia.org/wiki/Data_warehouse "Data warehouse")
* [Business intelligence](https://en.wikipedia.org/wiki/Business_intelligence "Business intelligence") |
|Data economy and exchange |* Data economy
* [Sharing](https://en.wikipedia.org/wiki/Data_sharing "Data sharing")
* [Open data](https://en.wikipedia.org/wiki/Open_data "Open data")
* [Philanthropy](https://en.wikipedia.org/wiki/Data_philanthropy "Data philanthropy")
* [Data as a service](https://en.wikipedia.org/wiki/Data_as_a_service "Data as a service")
* [Data broker](https://en.wikipedia.org/wiki/Data_broker "Data broker")
* Responsible reuse |
|Exchange, use, and public context |* [Exhaust](https://en.wikipedia.org/wiki/Data_exhaust "Data exhaust")
* [Farming](https://en.wikipedia.org/wiki/Data_farming "Data farming")
* [Archaeology](https://en.wikipedia.org/wiki/Data_archaeology "Data archaeology") |
|Distributed data, domains, and digital twins |* [Data mesh](https://en.wikipedia.org/wiki/Data_mesh "Data mesh")
* [Data product](https://en.wikipedia.org/wiki/Data_product "Data product")
* [Data domains](https://en.wikipedia.org/wiki/Data_domain "Data domain")
* Data categories
* [Data digital twins](https://en.wikipedia.org/wiki/Digital_twin "Digital twin")
* Digital thread
* Operational twins
* Analytical twins |
|Vendors and actors |* Data vendors
* Data technology vendors
* [Data service providers](https://en.wikipedia.org/wiki/Data_as_a_service "Data as a service")
* [Data brokers](https://en.wikipedia.org/wiki/Data_broker "Data broker")
* [Chief data officers](https://en.wikipedia.org/wiki/Chief_data_officer "Chief data officer")
* [Information professionals](https://en.wikipedia.org/wiki/Information_professional "Information professional")
* [Informatica](https://en.wikipedia.org/wiki/Informatica "Informatica")
* [IBM](https://en.wikipedia.org/wiki/IBM "IBM")
* [SAP](https://en.wikipedia.org/wiki/SAP "SAP")
* [Oracle](https://en.wikipedia.org/wiki/Oracle_Corporation "Oracle Corporation")
* [SAS](https://en.wikipedia.org/wiki/SAS_Institute "SAS Institute")
* [Qlik](https://en.wikipedia.org/wiki/Qlik "Qlik")
* [Experian](https://en.wikipedia.org/wiki/Experian "Experian")
* [Alation](https://en.wikipedia.org/wiki/Alation "Alation") |
|[Category](https://en.wikipedia.org/wiki/Category:Data "Category:Data") |

* [v](https://en.wikipedia.org/wiki/Template:Data_warehouses "Template:Data warehouses")
* [t](https://en.wikipedia.org/wiki/Template_talk:Data_warehouses "Template talk:Data warehouses")
* [e](https://en.wikipedia.org/wiki/Special:EditPage/Template:Data_warehouses "Special:EditPage/Template:Data warehouses")

[Data warehouses](https://en.wikipedia.org/wiki/Data_warehouse "Data warehouse")

Creating a data warehouse

|Concepts |* [Database](https://en.wikipedia.org/wiki/Database "Database")
* [Dimension](https://en.wikipedia.org/wiki/Dimension_\(data_warehouse\) "Dimension (data warehouse)")
* [Dimensional modeling](https://en.wikipedia.org/wiki/Dimensional_modeling "Dimensional modeling")
* [Fact](https://en.wikipedia.org/wiki/Fact_\(data_warehouse\) "Fact (data warehouse)")
* [OLAP](https://en.wikipedia.org/wiki/Online_analytical_processing "Online analytical processing")
* [Star schema](https://en.wikipedia.org/wiki/Star_schema "Star schema")
* [Snowflake schema](https://en.wikipedia.org/wiki/Snowflake_schema "Snowflake schema")
* [Reverse star schema](https://en.wikipedia.org/wiki/Reverse_star_schema "Reverse star schema")
* [Aggregate](https://en.wikipedia.org/wiki/Aggregate_\(data_warehouse\) "Aggregate (data warehouse)")
* [Single version of the truth](https://en.wikipedia.org/wiki/Single_version_of_the_truth "Single version of the truth") |
| --- | --- |
|Variants |* [Column-oriented DBMS](https://en.wikipedia.org/wiki/Column-oriented_DBMS "Column-oriented DBMS")
* [Data hub](https://en.wikipedia.org/wiki/Data_hub "Data hub")
* [Data mesh](https://en.wikipedia.org/wiki/Data_mesh "Data mesh")
* Ensemble modeling patterns
  
    + [Anchor modeling](https://en.wikipedia.org/wiki/Anchor_modeling "Anchor modeling")
    + [Data vault modeling](https://en.wikipedia.org/wiki/Data_vault_modeling "Data vault modeling")
    + [Focal point modeling](https://en.wikipedia.org/wiki/Focal_point_modeling?action=edit&redlink=1 "Focal point modeling (page does not exist)")
* [HOLAP](https://en.wikipedia.org/wiki/HOLAP "HOLAP")
* [MOLAP](https://en.wikipedia.org/wiki/MOLAP "MOLAP")
* [ROLAP](https://en.wikipedia.org/wiki/ROLAP "ROLAP")
* [Operational data store](https://en.wikipedia.org/wiki/Operational_data_store "Operational data store") |
|Elements |* [Data dictionary](https://en.wikipedia.org/wiki/Data_dictionary "Data dictionary") / [Metadata](https://en.wikipedia.org/wiki/Metadata "Metadata")
* [Data mart](https://en.wikipedia.org/wiki/Data_mart "Data mart")
* [Sixth normal form](https://en.wikipedia.org/wiki/Sixth_normal_form "Sixth normal form")
* [Surrogate key](https://en.wikipedia.org/wiki/Surrogate_key "Surrogate key") |
|Fact |* [Fact table](https://en.wikipedia.org/wiki/Fact_table "Fact table")
* [Early-arriving fact](https://en.wikipedia.org/wiki/Early-arriving_fact "Early-arriving fact")
* [Measure](https://en.wikipedia.org/wiki/Measure_\(data_warehouse\) "Measure (data warehouse)") |
|Dimension |* [Dimension table](https://en.wikipedia.org/wiki/Dimension_table "Dimension table")
* [Degenerate](https://en.wikipedia.org/wiki/Degenerate_dimension "Degenerate dimension")
* [Slowly changing](https://en.wikipedia.org/wiki/Slowly_changing_dimension "Slowly changing dimension") |
|Filling |* [Extract, transform, load (ETL)](https://en.wikipedia.org/wiki/Extract,_transform,_load)
* [Extract, load, transform (ELT)](https://en.wikipedia.org/wiki/Extract,_load,_transform "Extract, load, transform")
* [Extract](https://en.wikipedia.org/wiki/Data_extraction "Data extraction")
* [Transform](https://en.wikipedia.org/wiki/Data_transformation "Data transformation")
* [Load](https://en.wikipedia.org/wiki/Data_loading "Data loading") |

Using a data warehouse

|Concepts |* [Business intelligence](https://en.wikipedia.org/wiki/Business_intelligence "Business intelligence")
* [Dashboard](https://en.wikipedia.org/wiki/Dashboard_\(business\) "Dashboard (business)")
* [Data mining](https://en.wikipedia.org/wiki/Data_mining "Data mining")
* [Decision support system (DSS)](https://en.wikipedia.org/wiki/Decision_support_system "Decision support system")
* [OLAP cube](https://en.wikipedia.org/wiki/OLAP_cube "OLAP cube")
* [Data warehouse automation](https://en.wikipedia.org/wiki/Data_warehouse_automation "Data warehouse automation") |
| --- | --- |
|Languages |* [Data Mining Extensions (DMX)](https://en.wikipedia.org/wiki/Data_Mining_Extensions "Data Mining Extensions")
* [MultiDimensional eXpressions (MDX)](https://en.wikipedia.org/wiki/MultiDimensional_eXpressions "MultiDimensional eXpressions")
* [XML for Analysis (XMLA)](https://en.wikipedia.org/wiki/XML_for_Analysis "XML for Analysis") |
|Tools |* [Business intelligence software](https://en.wikipedia.org/wiki/Business_intelligence_software "Business intelligence software")
* [Reporting software](https://en.wikipedia.org/wiki/List_of_reporting_software "List of reporting software")
* [Spreadsheet](https://en.wikipedia.org/wiki/Spreadsheets "Spreadsheets") |

Related

|People |* [Bill Inmon](https://en.wikipedia.org/wiki/Bill_Inmon "Bill Inmon")
  
    + [Information factory](https://en.wikipedia.org/wiki/Corporate_information_factory "Corporate information factory")
* [Ralph Kimball](https://en.wikipedia.org/wiki/Ralph_Kimball "Ralph Kimball")
  
    + [Enterprise bus](https://en.wikipedia.org/wiki/Enterprise_bus_matrix "Enterprise bus matrix")
* [Dan Linstedt](https://en.wikipedia.org/wiki/Dan_Linstedt "Dan Linstedt") |
| --- | --- |
|Products |* [Comparison of OLAP servers](https://en.wikipedia.org/wiki/Comparison_of_OLAP_servers "Comparison of OLAP servers")
* [Data warehousing products and their producers](https://en.wikipedia.org/wiki/Category:Data_warehousing_products "Category:Data warehousing products") |