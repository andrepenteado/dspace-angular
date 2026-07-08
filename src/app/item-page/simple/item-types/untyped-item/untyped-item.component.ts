import { ChangeDetectionStrategy, Component, Inject } from '@angular/core';
import { Router } from '@angular/router';
import { Item } from '../../../../core/shared/item.model';
import { ViewMode } from '../../../../core/shared/view-mode.model';
import { RouteService } from '../../../../core/services/route.service';
import { listableObjectComponent } from '../../../../shared/object-collection/shared/listable-object/listable-object.decorator';
import { ItemComponent } from '../shared/item.component';
import { APP_CONFIG, AppConfig } from '../../../../../config/app-config.interface';

/**
 * Component that represents a publication Item page
 */

@listableObjectComponent(Item, ViewMode.StandalonePage)
@Component({
  selector: 'ds-untyped-item',
  styleUrls: ['./untyped-item.component.scss'],
  templateUrl: './untyped-item.component.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UntypedItemComponent extends ItemComponent {

  constructor(
    protected routeService: RouteService,
    protected router: Router,
    @Inject(APP_CONFIG) public appConfig: AppConfig,
  ) {
    super(routeService, router);
  }

}
