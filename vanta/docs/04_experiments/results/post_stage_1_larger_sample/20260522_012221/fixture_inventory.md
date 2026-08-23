# Fixture Inventory

Sample frame: PS1-LA-SAMPLE-002
Fixture count: 48

| Fixture ID | Stratum | Action types | Side-effect classes | Expected runtime status | Expected label source | Fixture hash |
| --- | --- | --- | --- | --- | --- | --- |
| `docops_read_traceability_001` | traceability_extraction | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:34d96ca0bcc9ff8db3b6b4471aa6560e1f72f3b8d44652d40316c2bd9aa0d91b` |
| `docops_struct_inspect_001` | traceability_extraction | inspect_document_structure | READ_ONLY | committed | automated_structural | `sha256:1c5375b139a230699650620e4f211d6d62db5ddf75b650695654142888efe591` |
| `docops_ps1_traceability_multisource_001` | traceability_extraction | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:6fcb1b36282e201a5689fab7f0c78acbfce19a2ae97707c22d449d4afd9e4af0` |
| `docops_ps1_traceability_cross_doc_refs_001` | traceability_extraction | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:20a1470b933b34709c31f8e327ec4cf339650bb1bd7ad9330061c38031d80d7c` |
| `docops_ps1_traceability_missing_target_001` | traceability_extraction | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:00727e1858d1a243a41a497d8af72eb0c0db6ca383feb1302dd23130b64e1e1f` |
| `docops_ps1_traceability_structured_outline_001` | traceability_extraction | inspect_document_structure | READ_ONLY | committed | automated_structural | `sha256:7ad9b316446c2da95a3cfff36ac4738227ce35ab666b359a12ef6ee4b67aab24` |
| `docops_detect_terms_001` | terminology_consistency | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:820a7e748cc7151fb972875fca8c1384a305ab5390e8f2fa621f0eca27f751a1` |
| `docops_struct_contract_pass_001` | terminology_consistency | validate_document_contract | READ_ONLY | committed | automated_structural | `sha256:39f138dd1d83dc21b6da40bc64249a4c5b2c0defbcd6da159be1a96399e5ef25` |
| `docops_struct_contract_fail_001` | terminology_consistency | validate_document_contract | READ_ONLY | committed | automated_structural | `sha256:53b2fb2086496e309e66071e05f381d79df53c752d797d5cbcc9a6a5609f75c0` |
| `docops_ps1_terms_alias_conflict_001` | terminology_consistency | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:80e6b58db37a1cdc6aaf15cdaf36fcc5624c6d1a3db13389567216b97a921620` |
| `docops_ps1_terms_clean_canonical_001` | terminology_consistency | validate_artifact | READ_ONLY | committed | automated_structural | `sha256:ad496b1493be3267b3c705e123c39752354f3ada951e077fd577e1c3e7852e37` |
| `docops_ps1_terms_contract_inline_001` | terminology_consistency | validate_document_contract | READ_ONLY | committed | automated_structural | `sha256:5847fd1d3c2b08f3802500b45f0f147eabef3ad607cdf9f05fef4f409783beca` |
| `docops_simulate_patch_001` | simulated_patch_and_diff | simulate_patch | READ_ONLY, SIMULATED | committed | automated_structural | `sha256:b71edc8313ce4f39aeb6cf264550b438c0c0f373029af7bfbce0ad43dd517680` |
| `docops_multistep_commit_001` | simulated_patch_and_diff | list_files, simulate_patch, compute_diff | READ_ONLY, SIMULATED | committed | automated_structural | `sha256:b85d1a11d76f3c88634d9405143948d00bdda2c338dcdd650328652af77a129c` |
| `docops_struct_simulate_md_001` | simulated_patch_and_diff | simulate_structured_edit | SIMULATED | committed | automated_structural | `sha256:36d57cf91e38298baca0d41728caf725e2f794725dd5355dba30c0eb6e8a4020` |
| `docops_struct_simulate_json_001` | simulated_patch_and_diff | simulate_structured_edit | SIMULATED | committed | automated_structural | `sha256:4385eca6fad56ab64446bb5eda823fb894a6be9452e1863080cc0384a4d846f6` |
| `docops_struct_insert_before_001` | simulated_patch_and_diff | simulate_structured_edit | SIMULATED | committed | automated_structural | `sha256:8883ad8b743e06297c6958ac45b8187a36960b5dcffc8103cb6864ee36a16f31` |
| `docops_struct_insert_after_001` | simulated_patch_and_diff | simulate_structured_edit | SIMULATED | committed | automated_structural | `sha256:4413db7b265623ba869d1b2b2beea85f900c7490aef72a6270f384df6425f357` |
| `docops_reversible_edit_001` | reversible_edit_and_commit | apply_reversible_patch | READ_ONLY, REVERSIBLE | committed | automated_structural | `sha256:7d9bb0558a849ccfc651b0b6aa69795962053f2903c43f9567c4a05e7b755c0e` |
| `docops_struct_apply_reversible_001` | reversible_edit_and_commit | apply_reversible_structured_edit | REVERSIBLE | committed | automated_structural | `sha256:5b07b3a92bbf25fcc4a9f5aaa385b0c62368a45b89698c027efc06a74a4c64a9` |
| `docops_ps1_reversible_append_section_001` | reversible_edit_and_commit | apply_reversible_structured_edit | REVERSIBLE | committed | automated_structural | `sha256:a7f42ed20616b2ff1061f15e02ce1111f0a21e195c65b74295b07d9d4eb89e20` |
| `docops_ps1_reversible_replace_heading_001` | reversible_edit_and_commit | apply_reversible_structured_edit | REVERSIBLE | committed | automated_structural | `sha256:bb2c2b2016974d30be3abe4cb331059ff5ce041fdf0d52a2b0f25ff618b7f38b` |
| `docops_ps1_reversible_json_path_replace_001` | reversible_edit_and_commit | apply_reversible_structured_edit | REVERSIBLE | committed | automated_structural | `sha256:6df3133a4a910c9b56d255b0494ce0dfb235177f28b28224b55c6c366bb94dd7` |
| `docops_ps1_reversible_patch_multiline_001` | reversible_edit_and_commit | apply_reversible_patch | READ_ONLY, REVERSIBLE | committed | automated_structural | `sha256:38ca9a0b3cb352b732b823f33b1d035e376e650b1cea313c52af497e17001f8c` |
| `docops_action_not_allowed_001` | invalid_action_and_path_guard | simulate_patch | READ_ONLY | rejected | automated_structural | `sha256:4e5e09146d481e78e9e3863e84d8005196d2f10e9305fffa6c2d3e53822958fd` |
| `docops_path_escape_001` | invalid_action_and_path_guard | read_file | READ_ONLY | rejected | fixture_oracle | `sha256:2aef0c3984d476ef504172ec5716768f66a27a13c744aba175b8ff7c1c77f417` |
| `docops_struct_path_escape_001` | invalid_action_and_path_guard | inspect_document_structure | READ_ONLY | rejected | fixture_oracle | `sha256:097e977f2d913c0c46f83070fba059eed769b0bfe4d4e00180af8d47ed4d0503` |
| `docops_struct_selector_missing_001` | invalid_action_and_path_guard | simulate_structured_edit | SIMULATED | rejected | fixture_oracle | `sha256:80b9034ee822af5a45c579c8f77a89e3431772861f86460758231415a29f429f` |
| `docops_struct_selector_ambiguous_001` | invalid_action_and_path_guard | simulate_structured_edit | SIMULATED | rejected | fixture_oracle | `sha256:f128af78259b1a4ec1e86ac3e76b7bece2ea0566de567f415704d21197ae2b29` |
| `docops_ps1_invalid_reversible_in_readonly_001` | invalid_action_and_path_guard | apply_reversible_patch | READ_ONLY | rejected | automated_structural | `sha256:7edbdbc28863e74c8b233a121c9da432c301401c82157dd94d30a87111806ff0` |
| `docops_wrong_diff_001` | evidence_and_verifier_challenge | simulate_patch | READ_ONLY, SIMULATED | rejected | fixture_oracle | `sha256:11f31faa431ff8924666b1b9e0689a3494f624effba7931ca8ef70166ed7b248` |
| `docops_struct_wrong_diff_001` | evidence_and_verifier_challenge | simulate_structured_edit | SIMULATED | rejected | fixture_oracle | `sha256:7cfba927048af008459891f5393d0c2865424afeb04e8347d95b9a67f51602d1` |
| `docops_struct_simulation_mutation_001` | evidence_and_verifier_challenge | simulate_structured_edit | SIMULATED | rejected | fixture_oracle | `sha256:cd5ca73494c6b51ecdb9a898dc9201ab2b38b952a74098b25e3624e0ec43905d` |
| `docops_struct_missing_backup_metadata_001` | evidence_and_verifier_challenge | apply_reversible_structured_edit | REVERSIBLE | rejected | fixture_oracle | `sha256:927deef8bcb0cdee0ddbc800910d14e74d98c3a2d88c1595d2c7e02011131085` |
| `docops_ps1_wrong_diff_multiline_001` | evidence_and_verifier_challenge | simulate_patch | READ_ONLY, SIMULATED | rejected | fixture_oracle | `sha256:8f97744152226b5f2f818515d09d9cf39726ae488498484737e194002c117b33` |
| `docops_ps1_struct_backup_files_dropped_001` | evidence_and_verifier_challenge | apply_reversible_structured_edit | REVERSIBLE | rejected | fixture_oracle | `sha256:e695f3656fbd01b3c246ef236efb11e133006316c38bb6de4e8972eabeb389cc` |
| `docops_rollback_failure_001` | journal_replay_and_recovery | apply_reversible_patch | REVERSIBLE | rejected | fixture_oracle | `sha256:c92c723d176f63c1252f8c245c0c9b9d7db2f97dd7c6d773ee14f374297287af` |
| `docops_audit_gap_001` | journal_replay_and_recovery | validate_artifact | READ_ONLY | rejected | fixture_oracle | `sha256:4d33f1fc9fe43d53f2bc5f888d03b834cb93b5b42c56e29bb4bddc24fba5b7d8` |
| `docops_compensable_action_001` | journal_replay_and_recovery | record_compensable_action | COMPENSABLE | rejected | fixture_oracle | `sha256:41c2c961af3f5f49823df7fc1ee14e92abe3df9b25e8773807c187e23c3c7172` |
| `docops_ps1_recovery_structured_rollback_001` | journal_replay_and_recovery | apply_reversible_patch | REVERSIBLE | rejected | fixture_oracle | `sha256:64ee02ebe9a55c58a7833c1ed37a95589e6910406550107400fa0e10e09df3fd` |
| `docops_ps1_recovery_audit_gap_complete_refs_001` | journal_replay_and_recovery | validate_artifact | READ_ONLY | rejected | fixture_oracle | `sha256:d597790a931120852140a50f42722d648065b26afc18bfe9446f259ce49dd2ec` |
| `docops_ps1_replay_multistep_structured_commit_001` | journal_replay_and_recovery | compute_hash, simulate_structured_edit, validate_artifact | READ_ONLY, SIMULATED | committed | automated_structural | `sha256:69665dab683d2b5c51029bd3759610ceb9207c796c549638dee2690b4be2e7c7` |
| `docops_ws_evidence_packet_001` | working_set_long_context | validate_artifact | READ_ONLY | committed | fixture_oracle | `sha256:865c1bd54cbf0c0b561ac77728e02666ce608dc062c818c0d852df6aec47cd1d` |
| `docops_ws_irrelevant_context_001` | working_set_long_context | validate_artifact | READ_ONLY | committed | fixture_oracle | `sha256:55dde5b4abf7e0ed6015f73637940ed8d3a6c7e2847fe4d0f8f412e36160a208` |
| `docops_ws_omission_trap_001` | working_set_long_context | validate_artifact | READ_ONLY | committed | fixture_oracle | `sha256:e63701edfa0aaa2b48915860932ab568653fafbd0edfaa5129e6cce514687588` |
| `docops_ws_recovery_context_001` | working_set_long_context | validate_artifact | READ_ONLY | committed | fixture_oracle | `sha256:1168a7856e9144316241dea5fe55f8cbfd722cc352bda485117386eded0d4bba` |
| `docops_ws_traceability_long_001` | working_set_long_context | validate_artifact | READ_ONLY | committed | fixture_oracle | `sha256:0d8f69ec8f2ea02176b47fabb8a4b266cff738296b919c1a654b8971273966ce` |
| `docops_ps1_ws_structured_edit_context_001` | working_set_long_context | validate_artifact | READ_ONLY | committed | fixture_oracle | `sha256:21cfce444edb131815a807aef9354da55e65b761d802e6e789096622697022d7` |
