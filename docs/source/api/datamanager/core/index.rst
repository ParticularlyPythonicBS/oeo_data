datamanager.core
================

.. py:module:: datamanager.core


Attributes
----------

.. autoapisummary::

   datamanager.core.console


Classes
-------

.. autoapisummary::

   datamanager.core.PermissionDict
   datamanager.core.VerificationResult


Functions
---------

.. autoapisummary::

   datamanager.core.get_r2_client
   datamanager.core.hash_file
   datamanager.core.upload_to_r2
   datamanager.core.download_from_r2
   datamanager.core.pull_and_verify
   datamanager.core.generate_sql_diff
   datamanager.core.delete_from_r2
   datamanager.core.verify_r2_access
   datamanager.core.upload_to_staging


Module Contents
---------------

.. py:data:: console

.. py:class:: PermissionDict

   Bases: :py:obj:`TypedDict`


   dict() -> new empty dictionary
   dict(mapping) -> new dictionary initialized from a mapping object's
       (key, value) pairs
   dict(iterable) -> new dictionary initialized as if via:
       d = {}
       for k, v in iterable:
           d[k] = v
   dict(**kwargs) -> new dictionary initialized with the name=value pairs
       in the keyword argument list.  For example:  dict(one=1, two=2)


   .. py:attribute:: read
      :type:  bool


   .. py:attribute:: write
      :type:  bool


   .. py:attribute:: delete
      :type:  bool


.. py:class:: VerificationResult

   Bases: :py:obj:`TypedDict`


   dict() -> new empty dictionary
   dict(mapping) -> new dictionary initialized from a mapping object's
       (key, value) pairs
   dict(iterable) -> new dictionary initialized as if via:
       d = {}
       for k, v in iterable:
           d[k] = v
   dict(**kwargs) -> new dictionary initialized with the name=value pairs
       in the keyword argument list.  For example:  dict(one=1, two=2)


   .. py:attribute:: bucket_name
      :type:  str


   .. py:attribute:: exists
      :type:  bool


   .. py:attribute:: permissions
      :type:  PermissionDict


   .. py:attribute:: message
      :type:  str


.. py:function:: get_r2_client() -> types_boto3_s3.client.S3Client

   Initializes and returns a boto3 S3 client for R2.


.. py:function:: hash_file(file_path: pathlib.Path) -> str

   Calculates and returns the SHA-256 hash of a file.


.. py:function:: upload_to_r2(client: types_boto3_s3.client.S3Client, file_path: pathlib.Path, object_key: str) -> None

   Uploads a file to R2 with a progress bar.


.. py:function:: download_from_r2(client: types_boto3_s3.client.S3Client, object_key: str, download_path: pathlib.Path) -> None

   Downloads a file from R2 with a progress bar.


.. py:function:: pull_and_verify(object_key: str, expected_hash: str, output_path: pathlib.Path) -> bool

   Downloads a file from R2, verifies its hash, and cleans up on failure.

   :returns: True if download and verification succeed, False otherwise.


.. py:function:: generate_sql_diff(old_file: pathlib.Path, new_file: pathlib.Path) -> tuple[str, str]

   Return (full_diff, summary) between two SQLite files.

   - If `sqldiff` CLI is available, use that for both full and summary.
   - Otherwise fall back to sqlite3 + difflib, and synthesize a summary.


.. py:function:: delete_from_r2(client: types_boto3_s3.client.S3Client, object_key: str) -> None

   Deletes an object from the R2 bucket.


.. py:function:: verify_r2_access() -> list[VerificationResult]

   Verifies granular permissions for both production and staging buckets.

   :returns: A list of result dictionaries, one for each bucket check.


.. py:function:: upload_to_staging(client: types_boto3_s3.client.S3Client, file_path: pathlib.Path, object_key: str) -> None

   Uploads a file to the STAGING R2 bucket with a progress bar.


