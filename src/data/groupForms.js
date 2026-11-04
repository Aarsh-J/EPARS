// Google Forms used to record data for EPARS.
// Each group is a section on the /forms page. To add a form, add an object to
// a group's `forms` list. A form with an empty `url` shows as "Link not added yet".
//
// Get each form's link from: Google Form -> Send -> link icon (the docs.google.com/forms/d/e/.../viewform URL).

export const FORM_GROUPS = [
  {
    id: "performance-outcomes",
    title: "Performance & Outcomes",
    description:
      "Record how work went, how it was judged, and how employees were rated. These feed the performance and assignment models.",
    forms: [
      {
        code: "F5",
        title: "Task Progress & Completion",
        who: "Assignee",
        description:
          "Update a task's status, how much is done, and (once finished) the completion date and hours.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSds4Ypl3kG7DyGyIAzQMID6HjA1kSngDg18AFgrcpgCqxKRuw/viewform",
      },
      {
        code: "F6",
        title: "Task Review & Quality",
        who: "Reviewer / Manager",
        description:
          "Review a completed task: quality, rework needed, overall rating and stakeholder satisfaction.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSfOJvXRLGlmueahdFdKdpuCYskMZDpwxhvbUVnUro5yq-3BYw/viewform",
      },
      {
        code: "F8",
        title: "Assignment Outcome & Feedback",
        who: "Manager + Assignee",
        description:
          "Say how an assignment turned out. Managers record success and quality; assignees record satisfaction.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSeJOLaSKLoqjYFk76TYNGQi3sQyTABDJrc0PGBnysex6wheVw/viewform",
      },
      {
        code: "F12",
        title: "Performance Review",
        who: "Employee + Manager",
        description:
          "Employees complete a self-assessment; managers complete the full review, ratings and recommendations.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSdYnGIbKxmr4ZqBQetYOTP7S0tVE62sDajW7n7lA-Qg3JD_eQ/viewform",
      },
      {
        code: "F13",
        title: "Peer / 360 Feedback",
        who: "Any employee",
        description:
          "Give a colleague specific, constructive feedback with ratings on quality, timeliness and collaboration.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSenPm9HL8c4ik02rU3e5YKvtzN3F0cb5iZ8fzzsU4HqEriaAw/viewform",
      },
      {
        code: "F13b",
        title: "Acknowledge Feedback",
        who: "Feedback recipient",
        description:
          "Confirm you have read feedback someone shared with you, and add a response if you like.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSdlLGFrp-qZZK00H2Z3o892iEd2qboufsfXxhQTLwnuymiKsg/viewform",
      },
    ],
  },

  {
    id: "people-wellbeing",
    title: "People & Wellbeing",
    description:
      "Describe who employees are, how much time they have, and how they are coping. These feed the burnout model and the employee records.",
    forms: [
      {
        code: "F1",
        title: "Employee Profile & Skills",
        who: "HR / Employee",
        description:
          "Create or update an employee record: role, department, seniority, skills, capacity and work preferences.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLScaMZ0LavxDqeGbG7nlA9iQz1Nz2c8PVLBlvGT_Cw-AV26tiw/viewform",
      },
      {
        code: "F2",
        title: "Availability & Leave",
        who: "Employee",
        description:
          "Record leave or out-of-office periods and whether you can take on new work.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSfvZfgBJI5I3bCT_DqhfkNBWQtgtl9riC7mqmtzXFGyJKowWQ/viewform",
      },
      {
        code: "F9",
        title: "Daily Timesheet & Work Context",
        who: "Employee",
        description:
          "Log your hours, overtime, where you worked and how the day felt. One entry per day.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSfnH3jUEsxSMoy-t1oyfvhSqoH6MzrdJAx38jvKbgttEP2Hsw/viewform",
      },
      {
        code: "F10",
        title: "Wellbeing Check-in",
        who: "Employee",
        description:
          "A short, confidential check-in on stress, energy and support, with an optional full monthly survey.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLScxkX-KFsl1cnXiRMEWTUmJDcILAA-oxA7N4-Ciw3mYDSRU_w/viewform",
      },
      {
        code: "F11",
        title: "Burnout Intervention Log",
        who: "Manager / HR",
        description:
          "Record the support given to an employee at risk of burnout, and later whether it helped.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSeveCvi3urooXjw4VH7vE6igAFh5fBWWH7WODFG726CIo3VEQ/viewform",
      },
    ],
  },

  {
    id: "planning-scheduling",
    title: "Planning & Scheduling",
    description:
      "Set up projects, define tasks, respond to assignments, form teams, and schedule events. These feed the project management, task assignment, and team formation models.",
    forms: [
      {
        code: "F3",
        title: "Project Setup",
        who: "Project Manager",
        description:
          "Register a new project with its timeline, budget, manager, priority, and required skills.",
        url: "https://docs.google.com/forms/d/1dCZMKUY6n82PTivQv4hH5ed_rBS3RC7nYB5ajkqqXvA/viewform",
      },
      {
        code: "F4",
        title: "Task Definition",
        who: "Project Manager / Lead",
        description:
          "Define a new task with role requirements, story points, complexity, and dependencies.",
        url: "https://docs.google.com/forms/d/1HRE6zPI3XGhf_rjEfJnTdzoaS5yarascRzLuP_WpAFw/viewform",
      },
      {
        code: "F7",
        title: "Assignment Response",
        who: "Assignee",
        description:
          "Accept or decline a task assignment. Declining records the reassignment reason.",
        url: "https://docs.google.com/forms/d/1lDIuo5DHVqdPjRJgOnQnEvsR6gmBhzymTKENVOiRC7I/viewform",
      },
      // {
      //   code: "F14",
      //   title: "Team Setup",
      //   who: "Manager / Lead",
      //   description:
      //     "Formally establish a project team with a team lead, member roster, and formation method.",
      //   url: "https://docs.google.com/forms/d/1_RkQkr2StG8jovsJVp_hwKIL3imZytf900GaX2DZIf8/viewform",
      // },
      {
        code: "F15",
        title: "Event Details",
        who: "Organizer / Manager",
        description:
          "Schedule meetings and events across participants to update calendars and track workload.",
        url: "https://docs.google.com/forms/d/1dwOXrsGeDH1VBpUm0oOQRTwMbKZcc_zZMvnwfFX_1xk/viewform",
      },
      {
        code: "F15b",
        title: "Event Wrap-up",
        who: "Organizer / Manager",
        description:
          "Conclude events by gathering feedback and documenting outcomes.",
        url: "https://docs.google.com/forms/d/e/1FAIpQLSdlLGFrp-qZZK00H2Z3o892iEd2qboufsfXxhQTLwnuymiKsg/viewform",
      },
    ],
  },
];