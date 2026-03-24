# Profiles

Industry/role profiles that define the skills matrix categories and proficiency levels for a target role. Each profile is consumed by Phase 0 (profile selection) and Phase 2 (skills matrix discovery).

## Existing Profiles

| Profile | Target Roles |
|---------|-------------|
| `netsuite_administrator.md` | NetSuite Admin, NetSuite Consultant, ERP Analyst, Financial Controller, Accounting Manager |

## Creating a New Profile

Profiles are auto-generated during Phase 0 of the resume workflow when no matching profile exists. Claude will:

1. Search for 3-5 current job postings for the target role (or use user-provided postings)
2. Extract common skills and group them into 8-20 categories
3. Define proficiency levels using the standard 4-level system
4. Save the profile to `profiles/[role_slug].md`

See `system/profile-generation-guide.md` for the full generation protocol.

## Cloning an Existing Profile

When a candidate's target role is closely related to an existing profile, clone and tweak instead of generating from scratch:

1. Copy the source profile: `cp profiles/netsuite_administrator.md profiles/[new_role_slug].md`
2. Update the header (`# Profile:`, `**Industry:**`, `**Target Roles:**`)
3. Review each skill category:
   - Remove categories irrelevant to the new role
   - Rename categories whose focus needs to shift
   - Add 1-3 new categories for skills unique to the new role
4. Save and confirm with user

**When to clone vs. generate fresh:**
- Clone: source profile covers 60%+ of the target role's skill areas (e.g., Financial Controller from NetSuite Administrator)
- Generate fresh: target role is in a different domain or the overlap is less than 60%

## Profile Format

Each profile contains:
- Header: industry and target roles (plus a `**Source:** Knowledge-based` flag if not research-backed)
- Proficiency level table (4 levels: Expert, Advanced, Intermediate, Novice with hex color codes)
- Skills organized into category groups, each with a descriptive paragraph

Profile filenames use snake_case: `financial_controller.md`, `frontend_engineer.md`, `data_analyst.md`.

## Keeping Profiles Current

Profiles reflect the job market at the time they were created. If a profile is more than 12 months old and the role has evolved (e.g., new tools have become standard), refresh it:

- Re-run 3-5 current job postings through the generation protocol (see `system/profile-generation-guide.md`)
- Compare new skill categories against the existing profile
- Add new categories, retire obsolete ones, update proficiency descriptions as needed
- Note the refresh date in the profile header: `**Last Updated:**`

A cloned profile inherits the source profile's age. If the source is stale, refresh before cloning.
