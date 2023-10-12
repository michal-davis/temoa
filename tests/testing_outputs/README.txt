These are just "shunts" used as output targets for tests.  Nothing need be done with them, and they will be re-created
by the testing code if deleted.  (see conftest.py)

Currently, they are never read and their entire purpose is to prevent (as much as possible) the tests from modifying
the input databases during testing.