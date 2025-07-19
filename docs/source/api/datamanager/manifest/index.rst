datamanager.manifest
====================

.. py:module:: datamanager.manifest

.. autoapi-nested-parse::

   Handles all read and write operations for the manifest.json file.
   This module ensures that the manifest is handled safely and consistently.



Functions
---------

.. autoapisummary::

   datamanager.manifest.read_manifest
   datamanager.manifest.write_manifest
   datamanager.manifest.get_dataset
   datamanager.manifest.add_history_entry
   datamanager.manifest.update_latest_history_entry
   datamanager.manifest.get_version_entry
   datamanager.manifest.add_new_dataset
   datamanager.manifest.update_dataset


Module Contents
---------------

.. py:function:: read_manifest() -> list[dict[str, Any]]

   Reads the manifest.json file from disk.

   :returns: A list of dataset dictionaries. Returns an empty list if the
             manifest does not exist.


.. py:function:: write_manifest(data: list[dict[str, Any]]) -> None

   Writes the provided data structure to the manifest.json file.

   :param data: The list of dataset dictionaries to write to the file.


.. py:function:: get_dataset(name: str) -> Optional[dict[str, Any]]

   Finds and returns a single dataset from the manifest by its logical name.

   :param name: The 'fileName' of the dataset to find.

   :returns: The dataset dictionary if found, otherwise None.


.. py:function:: add_history_entry(name: str, new_entry: dict[str, Any]) -> None

   Adds a new version entry to the beginning of a dataset's history.

   This function is used to add the temporary placeholder before the final
   commit hash is known.

   :param name: The 'fileName' of the dataset to update.
   :param new_entry: The new history dictionary to prepend.


.. py:function:: update_latest_history_entry(name: str, final_entry: dict[str, Any]) -> None

   Replaces the most recent history entry of a dataset.

   This is used to amend the placeholder entry with the final, complete
   data after the commit has been made.

   :param name: The 'fileName' of the dataset to update.
   :param final_entry: The final history dictionary that will replace the
                       current latest entry.


.. py:function:: get_version_entry(dataset_name: str, version: str = 'latest') -> Optional[dict[str, Any]]

   Finds the history entry for a specific version of a dataset.

   :param dataset_name: The 'fileName' of the dataset.
   :param version: The version string (e.g., "v1") or "latest".

   :returns: The history entry dictionary if found, otherwise None.


.. py:function:: add_new_dataset(dataset_object: dict[str, Any]) -> None

   Appends a new dataset object to the manifest file.

   :param dataset_object: The complete dictionary for the new dataset.


.. py:function:: update_dataset(name: str, updated_dataset: dict[str, Any]) -> None

   Finds a dataset by name and replaces the entire object.
   Used for amending the commit hash after the initial commit.
