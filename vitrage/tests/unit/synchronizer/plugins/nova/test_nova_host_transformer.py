# Copyright 2016 - Alcatel-Lucent
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import datetime

from oslo_log import log as logging

from vitrage.common.constants import EdgeLabels
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import EntityType
from vitrage.common.constants import EventAction
from vitrage.common.constants import SynchronizerProperties as SyncProps
from vitrage.common.constants import SyncMode
from vitrage.common.constants import VertexProperties
from vitrage.synchronizer.plugins.nova.host.transformer import HostTransformer
from vitrage.synchronizer.plugins.nova.zone.transformer import ZoneTransformer
from vitrage.synchronizer.plugins import transformer_base as tbase
from vitrage.synchronizer.plugins.transformer_base import TransformerBase
from vitrage.tests import base
from vitrage.tests.mocks import mock_syncronizer as mock_sync

LOG = logging.getLogger(__name__)


class NovaHostTransformerTest(base.BaseTest):

    def setUp(self):
        super(NovaHostTransformerTest, self).setUp()

        self.transformers = {}
        zone_transformer = ZoneTransformer(self.transformers)
        self.transformers[EntityType.NOVA_ZONE] = zone_transformer

    def test_create_placeholder_vertex(self):
        LOG.debug('Nova host transformer test: Test create placeholder vertex')

        # Test setup
        host_name = 'host123'
        timestamp = datetime.datetime.utcnow()
        host_transformer = HostTransformer(self.transformers)

        # Test action
        properties = {
            VertexProperties.ID: host_name,
            VertexProperties.SAMPLE_TIMESTAMP: timestamp
        }
        placeholder = host_transformer.create_placeholder_vertex(properties)

        # Test assertions
        observed_id_values = placeholder.vertex_id.split(
            TransformerBase.KEY_SEPARATOR)
        expected_id_values = host_transformer.key_values(host_name)
        self.assertEqual(tuple(observed_id_values), expected_id_values)

        observed_time = placeholder.get(VertexProperties.SAMPLE_TIMESTAMP)
        self.assertEqual(observed_time, timestamp)

        observed_subtype = placeholder.get(VertexProperties.TYPE)
        self.assertEqual(observed_subtype, host_transformer.HOST_TYPE)

        observed_entity_id = placeholder.get(VertexProperties.ID)
        self.assertEqual(observed_entity_id, host_name)

        observed_category = placeholder.get(VertexProperties.CATEGORY)
        self.assertEqual(observed_category, EntityCategory.RESOURCE)

        is_placeholder = placeholder.get(VertexProperties.IS_PLACEHOLDER)
        self.assertEqual(is_placeholder, True)

    def test_key_values(self):

        LOG.debug('Test key values')

        # Test setup
        host_name = 'host123456'
        host_transformer = HostTransformer(self.transformers)

        # Test action
        observed_key_fields = host_transformer.key_values(host_name)

        # Test assertions
        self.assertEqual(EntityCategory.RESOURCE, observed_key_fields[0])
        self.assertEqual(host_transformer.HOST_TYPE, observed_key_fields[1])
        self.assertEqual(host_name, observed_key_fields[2])

    def test_snapshot_transform(self):
        LOG.debug('Nova host transformer test: transform entity event')

        # Test setup
        spec_list = mock_sync.simple_host_generators(zone_num=2,
                                                     host_num=4,
                                                     snapshot_events=5)

        host_events = mock_sync.generate_random_events_list(spec_list)

        for event in host_events:
            # Test action
            wrapper = HostTransformer(self.transformers).transform(event)

            # Test assertions
            self._validate_vertex_props(wrapper.vertex, event)

            neighbors = wrapper.neighbors
            self.assertEqual(1, len(neighbors))
            self._validate_zone_neighbor(neighbors[0], event)

            if SyncMode.SNAPSHOT == event[SyncProps.SYNC_MODE]:
                self.assertEqual(EventAction.UPDATE_ENTITY, wrapper.action)
            else:
                self.assertEqual(EventAction.CREATE_ENTITY, wrapper.action)

    def _validate_zone_neighbor(self, zone, event):

        sync_mode = event[SyncProps.SYNC_MODE]
        zone_name = tbase.extract_field_value(
            event,
            HostTransformer(self.transformers).ZONE_NAME[sync_mode]
        )
        time = event[SyncProps.SAMPLE_DATE]

        zt = self.transformers[EntityType.NOVA_ZONE]
        properties = {
            VertexProperties.ID: zone_name,
            VertexProperties.SAMPLE_TIMESTAMP: time
        }
        expected_neighbor = zt.create_placeholder_vertex(properties)
        self.assertEqual(expected_neighbor, zone.vertex)

        # Validate neighbor edge
        edge = zone.edge
        self.assertEqual(edge.source_id, zone.vertex.vertex_id)
        self.assertEqual(
            edge.target_id,
            HostTransformer(self.transformers).extract_key(event)
        )
        self.assertEqual(edge.label, EdgeLabels.CONTAINS)

    def _validate_vertex_props(self, vertex, event):

        sync_mode = event[SyncProps.SYNC_MODE]
        extract_value = tbase.extract_field_value

        expected_id = extract_value(
            event,
            HostTransformer(self.transformers).HOST_NAME[sync_mode]
        )
        observed_id = vertex[VertexProperties.ID]
        self.assertEqual(expected_id, observed_id)
        self.assertEqual(
            EntityCategory.RESOURCE,
            vertex[VertexProperties.CATEGORY]
        )

        self.assertEqual(
            HostTransformer(self.transformers).HOST_TYPE,
            vertex[VertexProperties.TYPE]
        )

        expected_timestamp = event[SyncProps.SAMPLE_DATE]
        observed_timestamp = vertex[VertexProperties.SAMPLE_TIMESTAMP]
        self.assertEqual(expected_timestamp, observed_timestamp)

        expected_name = extract_value(
            event,
            HostTransformer.HOST_NAME[sync_mode]
        )
        observed_name = vertex[VertexProperties.NAME]
        self.assertEqual(expected_name, observed_name)

        is_placeholder = vertex[VertexProperties.IS_PLACEHOLDER]
        self.assertFalse(is_placeholder)

        is_deleted = vertex[VertexProperties.IS_DELETED]
        self.assertFalse(is_deleted)

    def test_extract_action_type(self):
        LOG.debug('Test extract action type')

        # Test setup
        spec_list = mock_sync.simple_host_generators(
            zone_num=1,
            host_num=1,
            snapshot_events=1,
            snap_vals={SyncProps.SYNC_MODE: SyncMode.SNAPSHOT})

        hosts_events = mock_sync.generate_random_events_list(spec_list)
        host_transformer = HostTransformer(self.transformers)

        # Test action
        action = host_transformer._extract_action_type(hosts_events[0])

        # Test assertion
        self.assertEqual(EventAction.UPDATE_ENTITY, action)

        # Test setup
        spec_list = mock_sync.simple_host_generators(
            zone_num=1,
            host_num=1,
            snapshot_events=1,
            snap_vals={SyncProps.SYNC_MODE: SyncMode.INIT_SNAPSHOT})
        hosts_events = mock_sync.generate_random_events_list(spec_list)
        host_transformer = HostTransformer(self.transformers)

        # Test action
        action = host_transformer._extract_action_type(hosts_events[0])

        # Test assertions
        self.assertEqual(EventAction.CREATE_ENTITY, action)

        # TODO(lhartal): To add extract action from update event