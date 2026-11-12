from src import crm

# Simulated drift: three stale records, like real CRM data going out of date.

# 1. Maplewood: wrong zip (website says 44280)
crm.update_account("001L3LGR6W69J8DYYV", {"billing_zip": "44299"})

# 2. Saline: wrong account name (website says "Bellhaven of Saline")
crm.update_account("001MVVAPY6U5TVYRC4", {"name": "Saline Nursing Home"})

# 3. Wooster: moved under the wrong parent, Stonebridge (website says Bellhaven)
crm.update_account("001W5G121A7SMRP58M", {"parent_id": "00139TNDS8HNLUZ5A6"})

print("drift applied: Maplewood zip, Saline name, Wooster parent")