1. there used to be no error handling.
2. In one version of implementation, the seq num does not properly increase.
3. In another version the seq num increases even on resending.
4. Not enough error case handling in urls.
5. global lock on db concurrent access. not dangerous, but can be slow.
6. Both order creation and ups id association can be in the same AUMessage, which can be confusing for UPS to handle.
7. Recv() from world and ups can be wrong if the message is over 1024 bytes.
8. In one version, error messages are not acked, and the errorous requests will continue to send.
9. With no prior ratings the average rating of a product is 0.
10. Not enough mechanisms to rebuild connections.
11. order status can be confusing.
12. Unused upsid column for user table. 
13. No warnings for failure associating ups id. But the order does not fail entirely if the sole error is upsid. 
14. package is stuck in warehouse unless enough number of packages is accumulated in a warehouse.

